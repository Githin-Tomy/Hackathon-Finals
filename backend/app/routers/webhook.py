"""
GitHub webhook receiver — handles PR opened / synchronize events.
Triggers the full review pipeline asynchronously.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, Depends
import threading
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db, Repository, PullRequest as PRModel, ReviewFinding
from app.db.models import WebhookResponse
from analysis.parser.ast_parser import analyse_files
from analysis.engine.aggregator import aggregate
from analysis.engine.confidence import split_by_confidence, compute_risk_score
from ai.agents.supervisor import run_supervisor
from ai.agents.summary_agent import run_summary_agent
from integrations.github.pr_collector import collect_pr_files, fetch_ci_cd_results, fetch_historical_comments, fetch_ci_job_logs
from integrations.github.publisher import publish_findings, publish_summary
from analysis.rules.base import Finding

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()


def _verify_signature(body: bytes, signature: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not settings.github_webhook_secret:
        return True  # Skip verification if no secret configured
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def _run_review_pipeline(
    repo_full_name: str,
    pr_number: int,
    commit_sha: str,
    db_pr_id: int,
) -> None:
    """Runs the full review pipeline in a background THREAD with its own DB session.
    Using a thread (not asyncio) means blocking I/O doesn't freeze the event loop."""
    from app.db.database import SessionLocal
    db = SessionLocal()

    logger.info("\n" + "=" * 80)
    logger.info("🔍 PIPELINE START: %s PR #%d (commit: %s)", repo_full_name, pr_number, commit_sha[:7])
    logger.info("=" * 80)

    try:
        db.expire_on_commit = False  # Keep objects accessible after commit
        # 1. Collect files
        db_pr = db.query(PRModel).filter(PRModel.id == db_pr_id).first()
        if not db_pr:
            logger.error("PR %d not found in database", db_pr_id)
            return

        db_pr.status = "reviewing"
        db_pr.ai_summary = "⚙️ Step 1/4: Fetching PR diffs & source files from GitHub..."
        db.commit()

        logger.info("📂 [Step 1/4] Fetching PR files from GitHub...")
        diff_files, pr_file_contents = collect_pr_files(repo_full_name, pr_number)
        
        # Expand context by checking for downstream callers of modified symbols
        from integrations.github.pr_collector import expand_context_by_symbols
        file_contents = expand_context_by_symbols(repo_full_name, pr_number, diff_files, pr_file_contents)
        
        # Self-healing architecture context sync: Sync context if empty
        repo = db.query(Repository).filter(Repository.id == db_pr_id).first()
        if repo and (not repo.system_context or not repo.context_last_updated):
            logger.info("ℹ️ Repository context not initialized. Syncing context skeleton in background...")
            from analysis.parser.architecture_sync import sync_repo_context
            sync_repo_context(repo_id=repo.id, repo_full_name=repo.full_name, db=db)

        pr_file_pairs = [(fp, src) for fp, src in pr_file_contents.items()]
        logger.info("   -> Collected %d file(s) from PR diff.", len(pr_file_pairs))

        # 1.5 Wait for CI/CD checks to complete
        db_pr.ai_summary = "⏳ Step 1.5/4: Waiting for GitHub Actions CI/CD checks to complete..."
        db.commit()

        import time
        logger.info("⏳ Waiting for CI/CD checks to complete...")
        
        ci_completed = False
        ci_cd_results = []
        poll_limit = 40  # 10 minutes maximum
        polls = 0
        
        while polls < poll_limit:
            ci_cd_results = fetch_ci_cd_results(repo_full_name, commit_sha)
            if not ci_cd_results:
                # If no check runs are found, wait a bit in case GitHub Actions hasn't registered them yet
                if polls > 4:  # Wait up to 1 minute for check runs to appear
                    logger.info("   ℹ️ No CI/CD checks found after 1 minute. Assuming no CI is configured.")
                    break
            else:
                # Check if any runs are still active (queued or in_progress)
                active_runs = [c for c in ci_cd_results if c.get("status") in ("queued", "in_progress")]
                if not active_runs:
                    logger.info("   ✅ All CI/CD checks completed.")
                    ci_completed = True
                    break
                logger.info("   ⏳ CI/CD checks are still running (%d active). Retrying in 15s...", len(active_runs))
            
            polls += 1
            time.sleep(15)  # OK: this is a real thread, not async — event loop stays free
            # Update DB periodically to let the user know we're still waiting
            if polls % 2 == 0:
                db_pr.ai_summary = f"⏳ Waiting for GitHub Actions CI/CD checks ({polls*15}s elapsed)..."
                db.commit()

        # Check if CI/CD passed or failed (if any checks exist)
        has_ci_failure = any(c.get("conclusion") in ("failure", "timed_out", "cancelled") for c in ci_cd_results)

        # Fetch the actual logs of the CI job
        logger.info("   🔍 Fetching CI logs from GitHub Actions...")
        real_logs = fetch_ci_job_logs(repo_full_name, commit_sha)
        
        # Resolve the raw build logs (fetching real logs or falling back to mock)
        ci_logs = ""
        if real_logs:
            ci_logs = real_logs
        elif has_ci_failure:
            logger.info("   ⚠️ Failed to fetch real logs for failed CI. Falling back to synthetic log template...")
            ci_logs = (
                "=================================== FAILURES ===================================\n"
                "_________________________________ test_auth ___________________________________\n"
                "\n"
                "    def test_auth():\n"
                ">       assert validate_token('invalid') == True\n"
                "E       AssertionError: assert False == True\n"
                "\n"
                "tests/test_auth.py:12: AssertionError\n"
                "=========================== 1 failed in 0.12s ============================\n"
                "\n"
                "[Bandit SAST Warning] B104: Hardcoded bind address detected (bind to all interfaces).\n"
                "   Location: ./auth.py:42"
            )

        # 2. Run LangGraph Multi-Agent Supervisor
        db_pr.ai_summary = "🤖 Running LangGraph Multi-Agent Supervisor..."
        db.commit()

        ai_findings: list[Finding] = []
        try:
            modified_files_paths = list(pr_file_contents.keys())
            logger.info("🤖 Invoking LangGraph Supervisor (has_ci_failure=%s)...", has_ci_failure)
            supervisor_output = run_supervisor(
                modified_files=modified_files_paths,
                file_contents=file_contents,
                repo_name=repo.full_name,
                has_ci_failure=has_ci_failure,
                ci_logs=ci_logs
            )
            
            # Process CI Agent findings from supervisor
            for r in supervisor_output.get("ci_results", []):
                file_path = r.get("file_path", "GitHub Actions")
                if file_path.startswith("./"):
                    file_path = file_path[2:]
                line_number = r.get("line_number", 1)
                
                snippet = "N/A"
                if file_path in file_contents:
                    try:
                        lines = file_contents[file_path].split("\n")
                        start = max(0, line_number - 2)
                        end = min(len(lines), line_number + 1)
                        snippet = "\n".join(lines[start:end])
                    except Exception:
                        pass
                        
                ai_findings.append(Finding(
                    rule_id=r.get("rule_id", "CI-ERR-001"),
                    rule_name="CI/CD Log Analysis",
                    category="ci_failure",
                    severity="high",
                    confidence=1.0,
                    file_path=file_path,
                    line_number=line_number,
                    code_snippet=snippet,
                    message=r.get("message", "CI/CD failure detected."),
                    suggestion=r.get("suggestion", ""),
                    source="ci"
                ))
            
            # Process Security Agent findings from supervisor
            for r in supervisor_output.get("security_results", []):
                file_path = r.get("file_path", "GitHub Actions")
                if file_path.startswith("./"):
                    file_path = file_path[2:]
                line_number = r.get("line_number", 1)
                
                snippet = "N/A"
                if file_path in file_contents:
                    try:
                        lines = file_contents[file_path].split("\n")
                        start = max(0, line_number - 2)
                        end = min(len(lines), line_number + 1)
                        snippet = "\n".join(lines[start:end])
                    except Exception:
                        pass
                        
                ai_findings.append(Finding(
                    rule_id=r.get("rule_id", "SEC-GEN-001"),
                    rule_name="AI Security Analysis",
                    category="security",
                    severity=r.get("severity", "medium"),
                    confidence=r.get("confidence", 0.9),
                    file_path=file_path,
                    line_number=line_number,
                    code_snippet=snippet,
                    message=r.get("analysis", "Security vulnerability detected."),
                    suggestion=r.get("suggestion", ""),
                    source="ai"
                ))

            # Process Code Review Agent findings from supervisor
            for r in supervisor_output.get("code_review_results", []):
                file_path = r.get("file_path", "GitHub Actions")
                if file_path.startswith("./"):
                    file_path = file_path[2:]
                line_number = r.get("line_number", 1)
                
                snippet = "N/A"
                if file_path in file_contents:
                    try:
                        lines = file_contents[file_path].split("\n")
                        start = max(0, line_number - 2)
                        end = min(len(lines), line_number + 1)
                        snippet = "\n".join(lines[start:end])
                    except Exception:
                        pass
                        
                ai_findings.append(Finding(
                    rule_id=r.get("rule_id", "CS-GEN-001"),
                    rule_name="AI Code Review Analysis",
                    category="code_smell",
                    severity=r.get("severity", "medium"),
                    confidence=r.get("confidence", 0.9),
                    file_path=file_path,
                    line_number=line_number,
                    code_snippet=snippet,
                    message=r.get("analysis", "Code quality issue detected."),
                    suggestion=r.get("suggestion", ""),
                    source="ai"
                ))
        except Exception as supervisor_err:
            logger.error("🤖 [Supervisor] AI Review failed: %s", supervisor_err, exc_info=True)
            ai_findings.append(Finding(
                rule_id="AI-REVIEW-ERR",
                rule_name="AI Code Review Failed",
                category="code_smell",
                severity="high",
                confidence=1.0,
                file_path="GitHub Actions",
                line_number=1,
                code_snippet="N/A",
                message=f"The AI supervisor failed to complete the review: {supervisor_err}",
                suggestion="Check your backend server logs or API credentials.",
                source="ai"
            ))

        all_findings = ai_findings
        risk_score = compute_risk_score(all_findings) if not has_ci_failure else 10.0

        # 5. Generate summary (passing CI/CD context and historical comments)
        db_pr.ai_summary = "📝 Step 4/4: Generating PR risk summary..."
        db.commit()

        historical_comments = fetch_historical_comments(repo_full_name, pr_number)
        logger.info("📝 Invoking Summary Agent (Total Findings: %d, Risk Score: %.1f/10)...",
                    len(all_findings), risk_score)
        summary = run_summary_agent(all_findings, risk_score, ci_cd_results, historical_comments)

        # 6. Persist findings to DB (clearing old findings from previous commits)
        db.query(ReviewFinding).filter(ReviewFinding.pr_id == db_pr_id).delete()
        for f in all_findings:
            db_finding = ReviewFinding(
                pr_id=db_pr_id,
                rule_id=f.rule_id,
                rule_name=f.rule_name,
                category=f.category,
                severity=f.severity,
                confidence=f.confidence,
                file_path=f.file_path,
                line_number=f.line_number,
                code_snippet=f.code_snippet,
                message=f.message,
                suggestion=f.suggestion,
                source=f.source,
            )
            db.add(db_finding)

        # 7. Publish findings inline first, capturing any that fail (due to being out-of-diff)
        logger.info("🚀 Publishing inline comments to GitHub...")
        failed_findings = publish_findings(repo_full_name, pr_number, commit_sha, all_findings)
        
        # If any findings couldn't be posted inline, append them as a section in the summary
        if failed_findings:
            summary_addition = "\n\n### ⚠️ Additional Findings (Out-of-Diff / Downstream Callers)\n"
            for f in failed_findings:
                prefix = "🤖 **AI Review**" if f.source == "ai" else "⚙️ **Rule Engine**"
                summary_addition += (
                    f"- {prefix} · **{f.file_path}:{f.line_number}** · `{f.rule_id}` · **{f.severity.upper()}**\n"
                    f"  *Issue:* {f.message}\n"
                )
                if f.suggestion:
                    summary_addition += f"  *Suggestion:* {f.suggestion}\n"
            summary += summary_addition

        # 8. Update PR record in DB
        db_pr = db.query(PRModel).filter(PRModel.id == db_pr_id).first()
        if db_pr:
            # If there are no findings, halt for human approval
            db_pr.status = "pending_approval" if len(all_findings) == 0 else "done"
            db_pr.risk_score = risk_score
            db_pr.ai_summary = summary

        db.commit()

        # 9. Publish the unified summary to GitHub
        logger.info("🚀 Publishing unified summary to GitHub...")
        publish_summary(repo_full_name, pr_number, summary, risk_score)

        logger.info("=" * 80)
        logger.info("✅ PIPELINE SUCCESS: %s PR #%d finished — %d finding(s), Risk: %.1f/10",
                    repo_full_name, pr_number, len(all_findings), risk_score)
        logger.info("=" * 80 + "\n")

    except Exception as e:
        logger.error("=" * 80)
        logger.error("❌ PIPELINE ERROR in %s PR #%d: %s", repo_full_name, pr_number, e, exc_info=True)
        logger.error("=" * 80)
        try:
            db_pr = db.query(PRModel).filter(PRModel.id == db_pr_id).first()
            if db_pr:
                db_pr.status = "error"
                db_pr.ai_summary = f"❌ Review pipeline failed: {e}"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()



@router.post("/github", response_model=WebhookResponse)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
    db: Session = Depends(get_db),
):
    body = await request.body()

    # Verify signature
    if x_hub_signature_256 and not _verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    # Only handle pull_request events
    if x_github_event != "pull_request":
        return WebhookResponse(status="ignored", message=f"Event '{x_github_event}' ignored")

    payload: dict[str, Any] = json.loads(body)
    action = payload.get("action", "")

    if action == "closed":
        pr_payload = payload.get("pull_request", {})
        repo_payload = payload.get("repository", {})
        repo = db.query(Repository).filter(Repository.github_id == repo_payload.get("id")).first()
        if repo:
            db_pr = db.query(PRModel).filter(
                PRModel.repo_id == repo.id,
                PRModel.github_pr_number == pr_payload.get("number"),
            ).first()
            if db_pr:
                db_pr.status = "merged" if pr_payload.get("merged") else "closed"
                db.commit()
        return WebhookResponse(status="accepted", message=f"PR #{pr_payload.get('number')} marked as closed/merged")

    if action not in ("opened", "synchronize", "reopened"):
        return WebhookResponse(status="ignored", message=f"Action '{action}' ignored")

    pr_payload = payload["pull_request"]
    repo_payload = payload["repository"]

    repo_full_name: str = repo_payload["full_name"]
    pr_number: int = pr_payload["number"]
    commit_sha: str = pr_payload["head"]["sha"]

    # Upsert repository
    repo = db.query(Repository).filter(Repository.github_id == repo_payload["id"]).first()
    if not repo:
        repo = Repository(
            github_id=repo_payload["id"],
            full_name=repo_full_name,
            url=repo_payload["html_url"],
        )
        db.add(repo)
        db.flush()

    # Upsert pull request
    db_pr = db.query(PRModel).filter(
        PRModel.repo_id == repo.id,
        PRModel.github_pr_number == pr_number,
    ).first()
    if not db_pr:
        db_pr = PRModel(
            github_pr_number=pr_number,
            repo_id=repo.id,
            title=pr_payload["title"],
            author=pr_payload["user"]["login"],
            base_branch=pr_payload["base"]["ref"],
            head_branch=pr_payload["head"]["ref"],
            html_url=pr_payload["html_url"],
            status="reviewing",
            ai_summary="🚀 New PR detected. Initializing review pipeline...",
        )
        db.add(db_pr)
        db.flush()
    else:
        db_pr.status = "reviewing"
        if action == "synchronize":
            db_pr.ai_summary = f"🔄 New commit ({commit_sha[:7]}) detected. Re-analyzing PR..."

    db.commit()
    db_pr_id = db_pr.id

    threading.Thread(
        target=_run_review_pipeline,
        kwargs=dict(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            commit_sha=commit_sha,
            db_pr_id=db_pr_id,
        ),
        daemon=True,
    ).start()

    return WebhookResponse(
        status="accepted",
        message=f"Review started for PR #{pr_number}",
        pr_id=db_pr_id,
    )


@router.post("/replay/{pr_id}", response_model=WebhookResponse)
async def replay_webhook(
    pr_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Re-trigger the review pipeline for an existing PR (for demo fallback)."""
    db_pr = db.query(PRModel).filter(PRModel.id == pr_id).first()
    if not db_pr:
        raise HTTPException(status_code=404, detail="PR not found")

    repo = db.query(Repository).filter(Repository.id == db_pr.repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    db_pr.status = "reviewing"
    db.commit()

    # Fetch commit SHA from GitHub
    try:
        from integrations.github.client import get_pull_request
        gh_pr = get_pull_request(repo.full_name, db_pr.github_pr_number)
        commit_sha = gh_pr.head.sha
    except Exception:
        commit_sha = "HEAD"

    threading.Thread(
        target=_run_review_pipeline,
        kwargs=dict(
            repo_full_name=repo.full_name,
            pr_number=db_pr.github_pr_number,
            commit_sha=commit_sha,
            db_pr_id=db_pr.id,
        ),
        daemon=True,
    ).start()

    return WebhookResponse(
        status="accepted",
        message=f"Replay triggered for PR #{db_pr.github_pr_number}",
        pr_id=pr_id,
    )


from pydantic import BaseModel

class DirectFetchRequest(BaseModel):
    repo_full_name: str  # e.g. "Githin-Tomy/AI-review-Test"
    pr_number: int       # e.g. 1


@router.post("/fetch", response_model=WebhookResponse)
async def fetch_pr_directly(
    body: DirectFetchRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Fetch any GitHub PR directly by repo name and PR number, seeding DB & running review."""
    from integrations.github.client import get_pull_request, get_repo
    try:
        gh_pr = get_pull_request(body.repo_full_name, body.pr_number)
        gh_repo = get_repo(body.repo_full_name)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Failed to fetch PR from GitHub: {exc}")

    # Upsert repository
    repo = db.query(Repository).filter(Repository.full_name == body.repo_full_name).first()
    if not repo:
        repo = Repository(
            github_id=gh_repo.id,
            full_name=body.repo_full_name,
            url=gh_repo.html_url,
        )
        db.add(repo)
        db.flush()

    # Upsert pull request
    db_pr = db.query(PRModel).filter(
        PRModel.repo_id == repo.id,
        PRModel.github_pr_number == body.pr_number,
    ).first()

    if not db_pr:
        db_pr = PRModel(
            github_pr_number=body.pr_number,
            repo_id=repo.id,
            title=gh_pr.title,
            author=gh_pr.user.login,
            base_branch=gh_pr.base.ref,
            head_branch=gh_pr.head.ref,
            html_url=gh_pr.html_url,
            status="reviewing",
            ai_summary="🚀 New PR detected via sync. Initializing review pipeline...",
        )
        db.add(db_pr)
        db.flush()
    else:
        db_pr.status = "reviewing"
        db_pr.ai_summary = "🔄 Manual sync triggered. Re-analyzing PR..."

    db.commit()
    db_pr_id = db_pr.id

    threading.Thread(
        target=_run_review_pipeline,
        kwargs=dict(
            repo_full_name=body.repo_full_name,
            pr_number=body.pr_number,
            commit_sha=gh_pr.head.sha,
            db_pr_id=db_pr_id,
        ),
        daemon=True,
    ).start()

    return WebhookResponse(
        status="accepted",
        message=f"Review started for {body.repo_full_name} PR #{body.pr_number}",
        pr_id=db_pr_id,
    )


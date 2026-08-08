"""
Reviews API — endpoints for the React dashboard.
"""
from __future__ import annotations
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import get_db, PullRequest as PRModel, ReviewFinding, Repository
from app.db.models import PROut, PRSummary, FindingOut, RepoOut
from pydantic import BaseModel

class ApprovalRequest(BaseModel):
    comment: str = ""

router = APIRouter()


@router.get("/prs", response_model=List[PRSummary])
def list_pull_requests(
    repo_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    include_closed: bool = Query(False),
    sync: bool = Query(False),
    limit: int = Query(50, le=200),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """List pull requests. By default, shows active/open PRs and hides closed/merged ones."""
    if sync and background_tasks:
        _perform_github_sync(db, background_tasks)

    q = db.query(PRModel, func.count(ReviewFinding.id).label("finding_count"))\
          .outerjoin(ReviewFinding, PRModel.id == ReviewFinding.pr_id)\
          .group_by(PRModel.id)

    if repo_id:
        q = q.filter(PRModel.repo_id == repo_id)
    if status:
        q = q.filter(PRModel.status == status)
    elif not include_closed:
        q = q.filter(PRModel.status.notin_(["closed", "merged"]))

    prs = q.order_by(PRModel.created_at.desc()).limit(limit).all()

    result = []
    for pr, finding_count in prs:
        result.append(PRSummary(
            id=pr.id,
            github_pr_number=pr.github_pr_number,
            title=pr.title,
            author=pr.author,
            html_url=pr.html_url,
            status=pr.status,
            risk_score=pr.risk_score,
            finding_count=finding_count,
            ai_summary=pr.ai_summary,
            created_at=pr.created_at,
        ))
    return result


def _perform_github_sync(db: Session, background_tasks: BackgroundTasks) -> int:
    """Helper to pull open PRs live from GitHub and sync closed ones."""
    try:
        from integrations.github.client import get_github_client
        gh = get_github_client()
    except Exception:
        return 0

    repos_to_sync = []
    try:
        user_repos = list(gh.get_user().get_repos())
        for r in user_repos:
            repos_to_sync.append(r)
    except Exception:
        pass

    db_repos = db.query(Repository).all()
    for db_r in db_repos:
        if db_r.full_name not in [x.full_name for x in repos_to_sync]:
            try:
                r = gh.get_repo(db_r.full_name)
                repos_to_sync.append(r)
            except Exception:
                pass

    synced_count = 0
    from app.routers.webhook import _run_review_pipeline

    for gh_repo in repos_to_sync:
        repo_db = db.query(Repository).filter(Repository.full_name == gh_repo.full_name).first()
        if not repo_db:
            repo_db = Repository(
                github_id=gh_repo.id,
                full_name=gh_repo.full_name,
                url=gh_repo.html_url,
            )
            db.add(repo_db)
            db.flush()

        try:
            open_prs = list(gh_repo.get_pulls(state="open"))
        except Exception:
            continue

        open_numbers = set(p.number for p in open_prs)

        # Mark local DB PRs that are no longer open as closed/merged
        existing_db_prs = db.query(PRModel).filter(PRModel.repo_id == repo_db.id).all()
        for db_pr in existing_db_prs:
            if db_pr.github_pr_number not in open_numbers and db_pr.status not in ("closed", "merged"):
                try:
                    p = gh_repo.get_pull(db_pr.github_pr_number)
                    db_pr.status = "merged" if p.merged else "closed"
                except Exception:
                    db_pr.status = "closed"

        for gh_pr in open_prs:
            db_pr = db.query(PRModel).filter(
                PRModel.repo_id == repo_db.id,
                PRModel.github_pr_number == gh_pr.number,
            ).first()

            if not db_pr:
                synced_count += 1
                db_pr = PRModel(
                    github_pr_number=gh_pr.number,
                    repo_id=repo_db.id,
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

                background_tasks.add_task(
                    _run_review_pipeline,
                    repo_full_name=gh_repo.full_name,
                    pr_number=gh_pr.number,
                    commit_sha=gh_pr.head.sha,
                    db_pr_id=db_pr.id,
                    db=db,
                )

    db.commit()
    return synced_count


@router.post("/sync")
def sync_github_prs(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Manually trigger a live sync of all open PRs from GitHub."""
    count = _perform_github_sync(db, background_tasks)
    return {"status": "success", "synced_new_prs": count}



@router.get("/prs/{pr_id}", response_model=PROut)
def get_pull_request(pr_id: int, db: Session = Depends(get_db)):
    """Get full PR details with all findings. Always reads fresh from DB."""
    db.expire_all()  # Force SQLAlchemy to discard cached state and re-query
    pr = db.query(PRModel).filter(PRModel.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="Pull request not found")
    return pr


@router.get("/prs/{pr_id}/findings", response_model=List[FindingOut])
def get_findings(
    pr_id: int,
    category: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get findings for a PR with optional filters."""
    q = db.query(ReviewFinding).filter(ReviewFinding.pr_id == pr_id)
    if category:
        q = q.filter(ReviewFinding.category == category)
    if severity:
        q = q.filter(ReviewFinding.severity == severity)
    if source:
        q = q.filter(ReviewFinding.source == source)
    return q.order_by(ReviewFinding.severity).all()


@router.get("/prs/{pr_id}/checks")
def get_ci_checks(pr_id: int, db: Session = Depends(get_db)):
    """Fetch live CI/CD check run results and steps from GitHub for a PR's latest commit."""
    import logging
    logger = logging.getLogger(__name__)
    
    pr = db.query(PRModel).filter(PRModel.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    repo = db.query(Repository).filter(Repository.id == pr.repo_id).first()
    if not repo:
        return []
        
    try:
        from integrations.github.client import get_github_client
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        gh = get_github_client()
        
        # Determine auth token
        token = gh.requester.auth.token if hasattr(gh.requester.auth, 'token') else ""
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        gh_repo = gh.get_repo(repo.full_name)
        gh_pr = gh_repo.get_pull(pr.github_pr_number)
        head_sha = gh_pr.head.sha
        
        # 1. Fetch workflow runs for the head SHA
        runs_url = f"https://api.github.com/repos/{repo.full_name}/actions/runs?head_sha={head_sha}"
        r = requests.get(runs_url, headers=headers, verify=False)
        if r.status_code != 200:
            logger.warning("Failed to fetch workflow runs from GitHub: %s %s", r.status_code, r.text)
            return []
            
        runs_data = r.json()
        workflow_runs = runs_data.get("workflow_runs", [])
        
        results = []
        for run in workflow_runs:
            # 2. Fetch jobs for each run
            jobs_url = f"https://api.github.com/repos/{repo.full_name}/actions/runs/{run.get('id')}/jobs"
            job_r = requests.get(jobs_url, headers=headers, verify=False)
            if job_r.status_code == 200:
                jobs_data = job_r.json()
                for job in jobs_data.get("jobs", []):
                    steps = []
                    for step in job.get("steps", []):
                        steps.append({
                            "name": step.get("name"),
                            "status": step.get("status"),
                            "conclusion": step.get("conclusion"),
                            "number": step.get("number"),
                        })
                    results.append({
                        "name": job.get("name"),
                        "status": job.get("status"),
                        "conclusion": job.get("conclusion"),
                        "details_url": job.get("html_url"),
                        "steps": steps
                    })
        
        # Fallback to standard check runs if no workflow runs found
        if not results:
            for run in gh_repo.get_commit(head_sha).get_check_runs():
                results.append({
                    "name": run.name,
                    "status": run.status,
                    "conclusion": run.conclusion,
                    "details_url": run.details_url,
                    "steps": []
                })
                
        return results
    except Exception as exc:
        logger.error("Error fetching CI checks/steps: %s", exc, exc_info=True)
        return []


@router.get("/prs/{pr_id}/logs")
def get_ci_logs(pr_id: int, db: Session = Depends(get_db)):
    """Fetch raw CI/CD logs from GitHub Actions for a PR."""
    import logging
    logger = logging.getLogger(__name__)
    
    pr = db.query(PRModel).filter(PRModel.id == pr_id).first()
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    repo = db.query(Repository).filter(Repository.id == pr.repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repo not found")
        
    try:
        from integrations.github.client import get_github_client
        gh = get_github_client()
        gh_repo = gh.get_repo(repo.full_name)
        gh_pr = gh_repo.get_pull(pr.github_pr_number)
        commit_sha = gh_pr.head.sha
        
        from integrations.github.pr_collector import fetch_ci_job_logs
        logs = fetch_ci_job_logs(repo.full_name, commit_sha)
        return {"logs": logs}
    except Exception as exc:
        logger.error("Error retrieving CI/CD logs: %s", exc, exc_info=True)
        return {"logs": f"Error retrieving logs from GitHub: {exc}"}


@router.post("/prs/{pr_id}/approve")
def approve_pr(pr_id: int, payload: ApprovalRequest, db: Session = Depends(get_db)):
    """Human-in-the-loop endpoint to formally approve a clean PR via GitHub."""
    db_pr = db.query(PRModel).filter(PRModel.id == pr_id).first()
    if not db_pr:
        raise HTTPException(status_code=404, detail="PR not found")
        
    db_repo = db.query(Repository).filter(Repository.id == db_pr.repo_id).first()
    if not db_repo:
        raise HTTPException(status_code=404, detail="Repo not found")
        
    try:
        from integrations.github.client import get_pull_request
        pr = get_pull_request(db_repo.full_name, db_pr.github_pr_number)
        
        body = payload.comment if payload.comment else "✅ A human reviewer has verified and approved the AI's assessment."
        pr.create_review(body=body, event="APPROVE")
        
        db_pr.status = "approved"
        db.commit()
        return {"status": "success", "message": "PR approved"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@router.post("/prs/{pr_id}/reject")
def reject_pr(pr_id: int, payload: ApprovalRequest, db: Session = Depends(get_db)):
    """Human-in-the-loop endpoint to formally reject a PR via GitHub."""
    db_pr = db.query(PRModel).filter(PRModel.id == pr_id).first()
    if not db_pr:
        raise HTTPException(status_code=404, detail="PR not found")
        
    db_repo = db.query(Repository).filter(Repository.id == db_pr.repo_id).first()
    if not db_repo:
        raise HTTPException(status_code=404, detail="Repo not found")
        
    try:
        from integrations.github.client import get_pull_request
        pr = get_pull_request(db_repo.full_name, db_pr.github_pr_number)
        
        body = payload.comment if payload.comment else "❌ A human reviewer has requested changes based on the AI's assessment."
        pr.create_review(body=body, event="REQUEST_CHANGES")
        
        db_pr.status = "rejected"
        db.commit()
        return {"status": "success", "message": "PR rejected"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/repos", response_model=List[RepoOut])
def list_repos(db: Session = Depends(get_db)):
    return db.query(Repository).all()


@router.post("/repos/{repo_id}/sync-context")
def sync_repository_context(repo_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger background context sync for a repository (AST skeleton parsing & Chroma DB vector embedding)."""
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
        
    from analysis.parser.architecture_sync import sync_repo_context
    background_tasks.add_task(sync_repo_context, repo_id=repo.id, repo_full_name=repo.full_name, db=db)
    
    return {"status": "accepted", "message": f"Architecture context sync started for {repo.full_name}"}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Dashboard summary statistics."""
    total_prs = db.query(PRModel).count()
    reviewed_prs = db.query(PRModel).filter(PRModel.status == "done").count()
    total_findings = db.query(ReviewFinding).count()
    critical_findings = db.query(ReviewFinding).filter(ReviewFinding.severity == "critical").count()
    ai_findings = db.query(ReviewFinding).filter(ReviewFinding.source == "ai").count()
    rule_findings = db.query(ReviewFinding).filter(ReviewFinding.source == "rule").count()

    return {
        "total_prs": total_prs,
        "reviewed_prs": reviewed_prs,
        "total_findings": total_findings,
        "critical_findings": critical_findings,
        "ai_findings": ai_findings,
        "rule_findings": rule_findings,
    }

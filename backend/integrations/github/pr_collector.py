"""
PR Collector — fetches diff and full file contents for a PR, plus
CI/CD check results and historical review comments for AI context.
"""
from __future__ import annotations
import base64
import logging
from typing import Dict, List, Tuple

from github.PullRequest import PullRequest

from integrations.github.client import get_pull_request
from analysis.parser.diff_parser import DiffFile, build_diff_files, extract_changed_line_numbers

logger = logging.getLogger(__name__)


def collect_pr_files(
    repo_full_name: str,
    pr_number: int,
) -> Tuple[List[DiffFile], Dict[str, str]]:
    """
    Fetch all changed Python files in a PR.

    Returns:
        diff_files    — list of DiffFile objects (with patch metadata)
        file_contents — dict of {filename: full source text}
    """
    pr: PullRequest = get_pull_request(repo_full_name, pr_number)
    github_files = list(pr.get_files())
    diff_files = build_diff_files(github_files)

    file_contents: Dict[str, str] = {}
    repo = pr.base.repo

    for df in diff_files:
        # Only analyse Python files; skip deleted files (no content to review)
        if not df.filename.endswith(".py") or df.status == "removed":
            continue
        try:
            content_file = repo.get_contents(df.filename, ref=pr.head.sha)
            # get_contents can return a list for directories — take first item
            if isinstance(content_file, list):
                content_file = content_file[0]
            raw = base64.b64decode(content_file.content).decode("utf-8", errors="replace")
            file_contents[df.filename] = raw
            df.content = raw
        except Exception as exc:
            logger.warning("Could not fetch content for %s: %s", df.filename, exc)

    logger.info("Collected %d Python file(s) from PR #%d", len(file_contents), pr_number)
    return diff_files, file_contents


def expand_context_by_symbols(
    repo_full_name: str,
    pr_number: int,
    diff_files: List[DiffFile],
    file_contents: Dict[str, str]
) -> Dict[str, str]:
    """
    Scans the modified python files for changed symbols (functions/classes),
    finds other python files in the repository that use/call them,
    and downloads those caller files to expand the review context.
    """
    logger.info("   🔍 Starting symbol search context expansion...")
    import ast
    import re
    
    pr: PullRequest = get_pull_request(repo_full_name, pr_number)
    repo = pr.base.repo
    modified_symbols = set()
    
    # 1. Identify which symbols were modified in the PR diff
    for df in diff_files:
        if not df.filename.endswith(".py") or df.status == "removed":
            continue
        
        source = file_contents.get(df.filename)
        if not source:
            continue
            
        try:
            tree = ast.parse(source)
            changed_lines = extract_changed_line_numbers(df.patch)
            
            # Find function/class definitions that overlap with changed lines
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start = node.lineno
                    end = getattr(node, "end_lineno", start)
                    
                    # If any changed line lies within this node's range, it's modified!
                    if any(start <= line <= end for line in changed_lines):
                        modified_symbols.add(node.name)
        except Exception as e:
            logger.warning("Error parsing AST for %s: %s", df.filename, e)
            
    if not modified_symbols:
        logger.info("   ℹ️ No modified Python symbols detected in PR diff.")
        return file_contents

    logger.info("   👉 Found %d modified symbol(s): %s", len(modified_symbols), list(modified_symbols))
    
    # 2. Search GitHub for usages of these symbols in the repository
    from integrations.github.client import get_github_client
    gh = get_github_client()
    
    expanded_contents = dict(file_contents)
    expanded_count = 0
    
    for symbol in modified_symbols:
        # Ignore very generic or short symbols to avoid noise
        if len(symbol) < 3 or symbol in ("__init__", "main", "run", "setup", "test"):
            continue
            
        logger.info("      🔍 Searching code for usages of symbol: '%s'", symbol)
        
        found_paths = []
        
        # Try GitHub Code Search API first
        try:
            query = f"\"{symbol}\" repo:{repo_full_name} language:python"
            results = gh.search_code(query=query)
            for result_file in results.get_page(0):
                if result_file.path.endswith(".py"):
                    found_paths.append(result_file.path)
        except Exception as search_exc:
            logger.warning("      ⚠️ Error running search_code for symbol %s: %s", symbol, search_exc)
            
        # Fallback: if search API returned nothing, scan via git tree traversal (for unindexed/small repos)
        if not found_paths:
            logger.info("      ⚠️ Code search returned 0 results. Checking git tree fallback...")
            try:
                tree = repo.get_git_tree(sha=pr.head.sha, recursive=True)
                all_py_files = [el.path for el in tree.tree if el.path.endswith(".py") and el.type == "blob"]
                
                # Only fallback if the repo is reasonably small to avoid API timeout/rate limits
                if len(all_py_files) <= 40:
                    logger.info("      ℹ️ Small repo detected (%d python files). Running local content search...", len(all_py_files))
                    for py_path in all_py_files:
                        if py_path in expanded_contents:
                            # Already loaded, check symbol usage
                            if re.search(rf"\b{symbol}\b", expanded_contents[py_path]):
                                found_paths.append(py_path)
                        else:
                            # Not loaded yet, fetch and search
                            try:
                                content_file = repo.get_contents(py_path, ref=pr.head.sha)
                                if isinstance(content_file, list):
                                    content_file = content_file[0]
                                raw = base64.b64decode(content_file.content).decode("utf-8", errors="replace")
                                if re.search(rf"\b{symbol}\b", raw):
                                    # Cache it temporarily in case we need it
                                    expanded_contents[py_path] = raw
                                    found_paths.append(py_path)
                            except Exception as fetch_exc:
                                logger.warning("      ⚠️ Could not fetch %s for fallback check: %s", py_path, fetch_exc)
                else:
                    logger.warning("      ⚠️ Repo has %d python files (too large for fallback scan). Skipping.", len(all_py_files))
            except Exception as tree_exc:
                logger.warning("      ⚠️ Failed to run git tree fallback for symbol %s: %s", symbol, tree_exc)
                
        # Now fetch and commit caller files to expanded_contents
        for file_path in set(found_paths):
            if file_path not in file_contents: # Only download if not in original PR files
                try:
                    if file_path not in expanded_contents:
                        content_file = repo.get_contents(file_path, ref=pr.head.sha)
                        if isinstance(content_file, list):
                            content_file = content_file[0]
                        raw = base64.b64decode(content_file.content).decode("utf-8", errors="replace")
                        expanded_contents[file_path] = raw
                    expanded_count += 1
                    logger.info("      ➕ Added context file: %s (contains reference to %s)", file_path, symbol)
                except Exception as fetch_exc:
                    logger.warning("      ⚠️ Could not fetch contents of %s: %s", file_path, fetch_exc)
                    
    return expanded_contents



def get_pr_metadata(repo_full_name: str, pr_number: int) -> dict:
    """Return a lightweight dict of PR metadata (title, author, branches, URL)."""
    pr = get_pull_request(repo_full_name, pr_number)
    return {
        "number":      pr.number,
        "title":       pr.title,
        "author":      pr.user.login,
        "base_branch": pr.base.ref,
        "head_branch": pr.head.ref,
        "html_url":    pr.html_url,
    }


def fetch_ci_cd_results(repo_full_name: str, commit_sha: str) -> List[dict]:
    """
    Fetch GitHub Actions / CI check run results for a given commit SHA.

    Aligns with problem statement requirement:
      'build and test results from CI/CD systems'

    Returns a list of dicts with keys: name, status, conclusion, details_url.
    Returns [] on error (non-fatal — the review pipeline continues without it).
    """
    try:
        from integrations.github.client import get_github_client
        gh = get_github_client()
        repo = gh.get_repo(repo_full_name)
        commit = repo.get_commit(commit_sha)
        return [
            {
                "name":        run.name,
                "status":      run.status,
                "conclusion":  run.conclusion,
                "details_url": run.details_url,
            }
            for run in commit.get_check_runs()
        ]
    except Exception as exc:
        logger.warning("Could not fetch CI/CD results for %s: %s", commit_sha, exc)
        return []


def fetch_ci_job_logs(repo_full_name: str, commit_sha: str) -> str:
    """
    Fetch raw logs for the Actions job on the commit.
    Returns a string containing the logs (truncated if very long),
    or an empty string if it fails or finds nothing.
    """
    try:
        from integrations.github.client import get_github_client
        import requests
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        gh = get_github_client()
        repo = gh.get_repo(repo_full_name)
        
        # 1. Find the workflow run
        target_run = None
        # Fetch the first page of runs (newest first) and find the matching commit SHA
        try:
            for run in repo.get_workflow_runs().get_page(0):
                if run.head_sha == commit_sha:
                    target_run = run
                    if run.conclusion == "failure":
                        break
        except Exception as e:
            logger.warning("Error searching workflow runs page: %s. Trying direct traversal...", e)
            for run in repo.get_workflow_runs():
                if run.head_sha == commit_sha:
                    target_run = run
                    if run.conclusion == "failure":
                        break
        
        if not target_run:
            logger.warning("Could not find workflow run for commit %s", commit_sha)
            return ""

        # 2. Find the job in that run (prioritize failed job, fall back to first)
        job_id = None
        for job in target_run.jobs():
            if job.conclusion == "failure":
                job_id = job.id
                break
        if not job_id:
            jobs_list = list(target_run.jobs())
            if jobs_list:
                job_id = jobs_list[0].id
        
        if not job_id:
            logger.warning("Could not find any job in run %d", target_run.id)
            return ""

        # 3. Retrieve the logs using authenticated requests
        auth = gh._Github__requester._Requester__auth
        token = auth.token
        auth_header = f"Bearer {token}" if auth.token_type == "installation" else f"token {token}"
        headers = {
            "Authorization": auth_header,
            "Accept": "application/vnd.github+json"
        }
        
        log_url = f"https://api.github.com/repos/{repo_full_name}/actions/jobs/{job_id}/logs"
        res = requests.get(log_url, headers=headers, allow_redirects=True, verify=False)
        if res.status_code == 200:
            # Truncate logs to stay within context (keep the last 10,000 characters where tracebacks are)
            log_text = res.text
            if len(log_text) > 10000:
                log_text = "...[truncated]...\n" + log_text[-10000:]
            return log_text
        else:
            logger.warning("Failed to fetch log for job %d: HTTP %d", job_id, res.status_code)
            return ""
            
    except Exception as exc:
        logger.warning("Error fetching failed job logs for %s: %s", commit_sha, exc)
        return ""


def fetch_historical_comments(repo_full_name: str, pr_number: int) -> List[str]:
    """
    Fetch the last 10 human-authored review comments from a PR.

    Aligns with problem statement requirement:
      'historical code review comments'

    Provides context to the Summary Agent so it avoids repeating past feedback.
    Returns [] on error (non-fatal).
    """
    try:
        pr = get_pull_request(repo_full_name, pr_number)
        comments: List[str] = []

        # Issue (top-level) comments — exclude bot comments
        for comment in pr.get_issue_comments():
            if comment.user.type != "Bot":
                comments.append(f"{comment.user.login}: {comment.body}")

        # Formal review bodies — exclude bot reviews
        for review in pr.get_reviews():
            if review.user.type != "Bot" and review.body:
                comments.append(f"[{review.state}] {review.user.login}: {review.body}")

        # Return only the most recent 10 to stay within LLM context budget
        return comments[-10:]
    except Exception as exc:
        logger.warning("Could not fetch historical comments for PR #%d: %s", pr_number, exc)
        return []

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── Finding Schemas ──────────────────────────────────────────────────────────

class FindingBase(BaseModel):
    rule_id: str
    rule_name: str
    category: str
    severity: str
    confidence: float
    file_path: str
    line_number: int
    code_snippet: str
    message: str
    suggestion: str = ""
    source: str = "rule"


class FindingCreate(FindingBase):
    pr_id: int


class FindingOut(FindingBase):
    id: int
    pr_id: int
    comment_posted: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Pull Request Schemas ─────────────────────────────────────────────────────

class PRBase(BaseModel):
    github_pr_number: int
    title: str
    author: str
    base_branch: str
    head_branch: str
    html_url: str


class PRCreate(PRBase):
    repo_id: int


class PROut(PRBase):
    id: int
    repo_id: int
    status: str
    risk_score: Optional[float] = 0.0
    ai_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    findings: List[FindingOut] = []

    class Config:
        from_attributes = True


class PRSummary(BaseModel):
    """Lightweight PR summary for list views."""
    id: int
    github_pr_number: int
    title: str
    author: str
    html_url: str
    status: str
    risk_score: Optional[float] = 0.0
    ai_summary: Optional[str] = None
    finding_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Repository Schemas ───────────────────────────────────────────────────────

class RepoOut(BaseModel):
    id: int
    github_id: int
    full_name: str
    url: str
    system_context: Optional[str] = ""
    context_last_updated: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ── Eval Schemas ─────────────────────────────────────────────────────────────

class EvalResultOut(BaseModel):
    id: int
    fixture_name: str
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    run_at: datetime

    class Config:
        from_attributes = True


# ── Webhook Payload ──────────────────────────────────────────────────────────

class WebhookResponse(BaseModel):
    status: str
    message: str
    pr_id: Optional[int] = None

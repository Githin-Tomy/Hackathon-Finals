from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text,
    DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
from app.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if "sqlite" in settings.database_url else {}
engine = create_engine(
    settings.database_url,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ── DB Models ────────────────────────────────────────────────────────────────

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(Integer, unique=True, index=True)
    full_name = Column(String, unique=True, index=True)   # e.g. "owner/repo"
    url = Column(String)
    system_context = Column(Text, default="")
    context_last_updated = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    pull_requests = relationship("PullRequest", back_populates="repository")


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    github_pr_number = Column(Integer)
    repo_id = Column(Integer, ForeignKey("repositories.id"))
    title = Column(String)
    author = Column(String)
    base_branch = Column(String)
    head_branch = Column(String)
    html_url = Column(String)
    status = Column(String, default="pending")  # pending | reviewing | done
    risk_score = Column(Float, default=0.0)
    ai_summary = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    repository = relationship("Repository", back_populates="pull_requests")
    findings = relationship("ReviewFinding", back_populates="pull_request")


class ReviewFinding(Base):
    __tablename__ = "review_findings"

    id = Column(Integer, primary_key=True, index=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"))
    rule_id = Column(String)             # e.g. "SEC001"
    rule_name = Column(String)
    category = Column(String)            # security | code_smell | performance | architecture
    severity = Column(String)            # critical | high | medium | low
    confidence = Column(Float)           # 0.0 – 1.0
    file_path = Column(String)
    line_number = Column(Integer)
    code_snippet = Column(Text)
    message = Column(String)
    suggestion = Column(Text, default="")
    source = Column(String, default="rule")  # rule | ai
    comment_posted = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    pull_request = relationship("PullRequest", back_populates="findings")


class EvalResult(Base):
    __tablename__ = "eval_results"

    id = Column(Integer, primary_key=True, index=True)
    fixture_name = Column(String)
    precision = Column(Float)
    recall = Column(Float)
    f1 = Column(Float)
    true_positives = Column(Integer)
    false_positives = Column(Integer)
    false_negatives = Column(Integer)
    run_at = Column(DateTime, server_default=func.now())


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

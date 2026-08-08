"""
Eval API — runs the scoring harness against synthetic fixtures.
"""
from __future__ import annotations
import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db, EvalResult
from app.db.models import EvalResultOut
from eval.scoring import run_eval

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/run", response_model=List[EvalResultOut])
def trigger_eval(db: Session = Depends(get_db)):
    """Run the eval harness against all synthetic fixtures and store results."""
    results = run_eval()
    db_results = []
    for r in results:
        db_r = EvalResult(**r)
        db.add(db_r)
        db_results.append(db_r)
    db.commit()
    for r in db_results:
        db.refresh(r)
    return db_results


@router.get("/results", response_model=List[EvalResultOut])
def get_eval_results(db: Session = Depends(get_db)):
    """Return all stored eval results."""
    return db.query(EvalResult).order_by(EvalResult.run_at.desc()).all()

"""
Confidence scorer — routes findings to direct-publish vs AI-review path.
"""
from __future__ import annotations
from typing import List, Tuple

from analysis.rules.base import Finding
from app.config import get_settings

settings = get_settings()


def split_by_confidence(
    findings: List[Finding],
    threshold: float | None = None,
) -> Tuple[List[Finding], List[Finding]]:
    """
    Split findings into two lists:
    - high_confidence: confidence >= threshold  → publish directly as PR comment
    - low_confidence:  confidence <  threshold  → route to AI agent layer

    Returns (high_confidence, low_confidence).
    """
    threshold = threshold if threshold is not None else settings.confidence_threshold
    high: List[Finding] = []
    low: List[Finding] = []
    for f in findings:
        if f.confidence >= threshold:
            high.append(f)
        else:
            low.append(f)
    return high, low


def compute_risk_score(findings: List[Finding]) -> float:
    """
    Compute a 0–10 risk score for a PR based on its findings.
    Weighted by severity × confidence.
    """
    if not findings:
        return 0.0
    raw = sum(f.severity_weight() * f.confidence for f in findings)
    # Normalise: cap at 10
    return min(round(raw, 2), 10.0)

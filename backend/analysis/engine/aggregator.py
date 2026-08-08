"""
Finding aggregator — deduplication and grouping.
"""
from __future__ import annotations
from typing import List, Tuple

from analysis.rules.base import Finding


def deduplicate(findings: List[Finding]) -> List[Finding]:
    """
    Remove duplicate findings identified by (rule_id, file_path, line_number).
    Keeps the first occurrence (highest confidence expected if sorted).
    """
    seen: set[Tuple[str, str, int]] = set()
    unique: List[Finding] = []
    for f in findings:
        key = (f.rule_id, f.file_path, f.line_number)
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return unique


def sort_by_severity(findings: List[Finding]) -> List[Finding]:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(findings, key=lambda f: (order.get(f.severity, 4), -f.confidence))


def aggregate(findings: List[Finding]) -> List[Finding]:
    """
    Full aggregation pipeline:
    1. Deduplicate
    2. Sort by severity (critical first)
    """
    return sort_by_severity(deduplicate(findings))

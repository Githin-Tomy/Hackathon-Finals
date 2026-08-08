"""
Python AST parser — walks changed files and runs all registered rules.
"""
from __future__ import annotations
import ast
import logging
from typing import List, Optional, Tuple

from analysis.rules.base import Finding, registry
import analysis.rules as rules  # noqa: F401 — side-effect: registers all rules

logger = logging.getLogger(__name__)


def parse_file(source: str, file_path: str) -> Tuple[Optional[ast.AST], List[Finding]]:
    """
    Parse Python source into an AST.

    Returns (tree, findings).  findings will be non-empty only if
    the parse itself fails (syntax error finding).
    """
    try:
        tree = ast.parse(source, filename=file_path)
        return tree, []
    except SyntaxError as exc:
        return None, [
            Finding(
                rule_id="PARSE001",
                rule_name="Syntax Error",
                category="parse",
                severity="high",
                confidence=1.0,
                file_path=file_path,
                line_number=exc.lineno or 1,
                code_snippet=exc.text or "",
                message=f"Python syntax error: {exc.msg}",
                suggestion="Fix the syntax error before running the review.",
            )
        ]


def analyse_file(source: str, file_path: str) -> List[Finding]:
    """
    Full pipeline: parse → run all rules → return findings.
    Only runs on .py files.
    """
    if not file_path.endswith(".py"):
        return []

    tree, parse_findings = parse_file(source, file_path)
    if tree is None:
        return parse_findings

    rule_findings = registry.run_all(tree, file_path, source)
    all_findings = parse_findings + rule_findings
    logger.info("Analysed %s — %d findings", file_path, len(all_findings))
    return all_findings


def analyse_files(files: List[Tuple[str, str]]) -> List[Finding]:
    """
    Analyse multiple (file_path, source) pairs.
    """
    all_findings: List[Finding] = []
    for file_path, source in files:
        all_findings.extend(analyse_file(source, file_path))
    return all_findings

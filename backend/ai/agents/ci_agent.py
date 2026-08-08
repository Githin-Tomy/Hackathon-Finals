"""
CI/CD Failure Analyzer Agent
Analyzes historical/synthetic CI failure logs to pinpoint root causes.
"""
from __future__ import annotations
import logging
from typing import Any

from ai.llm import run_llm_agent
from analysis.rules.base import Finding

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert DevOps engineer and Python developer analyzing CI/CD build logs.
You will be provided with raw build logs (e.g. Pytest failures, assertion errors, Flake8 linting warnings, Bandit SAST security scans, or build tracebacks).

Your goal is to parse these logs and extract all failures and warnings.

Respond ONLY with a valid JSON object with a key "results" containing an array. Each element must have:
{
  "rule_id": "<a short identifier, e.g. PYTEST-FAIL, FLAKE8-E722, BANDIT-B104, CI-ERR-001>",
  "rule_name": "<human readable title, e.g. Unit Test Failure or Linter Warning>",
  "category": "<ci_failure|ci_warning|sast_warning>",
  "severity": "<critical|high|medium|low>",
  "file_path": "<file path relative to repo root, or 'GitHub Actions'>",
  "line_number": <line number integer, default 1 if unknown>,
  "message": "<detailed 1-2 sentence explanation of the test/build failure>",
  "suggestion": "<concrete fix recommendation or code snippet fix>"
}

Do not include any text outside the JSON object. If the logs are empty or no issues are found, return {"results": []}."""


def run_ci_agent(log_text: str) -> list[Finding]:
    """
    Analyzes a CI/CD log and returns a list of Finding objects representing failures and warnings.
    """
    logger.info("   🔍 [CIAgent] Analyzing CI failure/warning logs...")
    if not log_text or not log_text.strip():
        logger.warning("   ⚠️ [CIAgent] Log text is empty. Returning default CI failure finding.")
        return [
            Finding(
                rule_id="CI-ERR-001",
                rule_name="Continuous Integration Failure",
                category="ci_failure",
                severity="critical",
                confidence=1.0,
                file_path="GitHub Actions",
                line_number=1,
                code_snippet="N/A",
                message="GitHub Actions CI/CD check failed, but build logs were empty or unavailable.",
                suggestion="Inspect the failing build job directly in GitHub Actions.",
                source="ci",
            )
        ]

    try:
        raw_results = run_llm_agent(SYSTEM_PROMPT, f"CI BUILD LOGS:\n\n{log_text}", "🔍 [CIAgent]")
        findings: list[Finding] = []

        for r in raw_results:
            file_path = str(r.get("file_path", "GitHub Actions"))
            if file_path.startswith("./"):
                file_path = file_path[2:]

            line_num = 1
            try:
                line_num = int(r.get("line_number", 1))
            except (ValueError, TypeError):
                line_num = 1

            findings.append(
                Finding(
                    rule_id=str(r.get("rule_id", "CI-ERR-001")),
                    rule_name=str(r.get("rule_name", "CI/CD Log Analysis")),
                    category=str(r.get("category", "ci_failure")),
                    severity=str(r.get("severity", "high")),
                    confidence=0.99,
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet="N/A",
                    message=str(r.get("message", "CI/CD unit test or build failure detected.")),
                    suggestion=str(r.get("suggestion", "Fix the failing assertion or syntax error reported in the build log.")),
                    source="ci",
                )
            )

        if not findings:
            logger.info("   🔍 [CIAgent] LLM returned 0 findings. Creating fallback CI failure finding...")
            findings.append(
                Finding(
                    rule_id="CI-FAIL-001",
                    rule_name="Continuous Integration Failure",
                    category="ci_failure",
                    severity="critical",
                    confidence=1.0,
                    file_path="GitHub Actions",
                    line_number=1,
                    code_snippet="N/A",
                    message="Unit tests or build checks failed in GitHub Actions. Review the workflow output.",
                    suggestion="Check unit test assertions, dependencies, and environment setup.",
                    source="ci",
                )
            )

        logger.info("   🔍 [CIAgent] Successfully evaluated %d finding(s) from CI logs.", len(findings))
        return findings

    except Exception as exc:
        logger.error("   ❌ [CIAgent] Failed analyzing logs: %s", exc, exc_info=True)
        return [
            Finding(
                rule_id="CI-FAIL-001",
                rule_name="Continuous Integration Failure",
                category="ci_failure",
                severity="critical",
                confidence=1.0,
                file_path="GitHub Actions",
                line_number=1,
                code_snippet="N/A",
                message=f"Unit tests failed in CI/CD pipeline. Log analysis error: {exc}",
                suggestion="Inspect GitHub Actions workflow logs for exact failure details.",
                source="ci",
            )
        ]

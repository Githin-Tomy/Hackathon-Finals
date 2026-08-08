"""
CI/CD Failure Analyzer Agent
Analyzes historical/synthetic CI failure logs to pinpoint root causes.
"""
import logging
from langchain_core.messages import HumanMessage, SystemMessage

from ai.llm import get_llm
from analysis.rules.base import Finding

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert DevOps engineer and Python developer.
You will be provided with raw logs from a CI/CD build run (e.g. Flake8 linter warnings, Bandit SAST security scans, or Pytest test tracebacks).

Your goal is to parse these logs and extract:
1. ANY critical build failures (like python syntax errors, failing test assertions, or failed build steps).
2. ANY non-critical warnings (like unused variables, bare except blocks, formatting issues, or security alerts).

For EACH issue you find, format it exactly as follows:
---
SEVERITY: <critical | high | medium | low>
CATEGORY: <ci_failure | ci_warning | sast_warning>
RULE_ID: <a short identifier, e.g. FLAKE8-E722 or PYTEST-FAIL or BANDIT-B104>
FILE: <file_path_relative_to_repo_root>
LINE: <line_number_integer>
MESSAGE: <explanation of the issue>
SUGGESTION: <concrete, specific fix or code change recommended to resolve the error/warning>
---

If you find multiple issues, print multiple blocks separated by "---".
Do not include any other markdown text or wrapper. If the build succeeded and there are no warnings or failures at all in the log, output "NO_ISSUES"."""

def run_ci_agent(log_text: str) -> list[Finding]:
    """
    Analyzes a CI/CD log and returns a list of Finding objects representing failures and warnings.
    """
    logger.info("   🔍 [CIAgent] Analyzing CI failure/warning logs...")
    
    try:
        llm = get_llm()
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"CI BUILD LOGS:\n\n{log_text}"),
        ]
        response = llm.invoke(messages)
        raw_output = response.content.strip()
        
        logger.info("   🔍 [CIAgent] Parsing agent output...")
        
        if "NO_ISSUES" in raw_output:
            logger.info("   🔍 [CIAgent] No issues found in logs.")
            return []
            
        findings: list[Finding] = []
        blocks = raw_output.split("---")
        
        for block in blocks:
            block = block.strip()
            if not block or block == "---":
                continue
                
            lines = block.split("\n")
            severity = "medium"
            category = "ci_warning"
            rule_id = "CI-WARN-001"
            file_path = "GitHub Actions"
            line_number = 1
            message_lines = []
            suggestion_lines = []
            current_field = None
            
            for line in lines:
                line = line.strip()
                if line.startswith("SEVERITY:"):
                    severity = line.replace("SEVERITY:", "").strip().lower()
                    current_field = None
                elif line.startswith("CATEGORY:"):
                    category = line.replace("CATEGORY:", "").strip().lower()
                    current_field = None
                elif line.startswith("RULE_ID:"):
                    rule_id = line.replace("RULE_ID:", "").strip()
                    current_field = None
                elif line.startswith("FILE:"):
                    val = line.replace("FILE:", "").strip()
                    if val.startswith("./"):
                        val = val[2:]
                    file_path = val
                    current_field = None
                elif line.startswith("LINE:"):
                    try:
                        line_number = int(line.replace("LINE:", "").strip())
                    except ValueError:
                        pass
                    current_field = None
                elif line.startswith("MESSAGE:"):
                    current_field = "message"
                    val = line.replace("MESSAGE:", "").strip()
                    if val:
                        message_lines.append(val)
                elif line.startswith("SUGGESTION:"):
                    current_field = "suggestion"
                    val = line.replace("SUGGESTION:", "").strip()
                    if val:
                        suggestion_lines.append(val)
                elif current_field == "message":
                    message_lines.append(line)
                elif current_field == "suggestion":
                    suggestion_lines.append(line)
            
            message = " ".join(message_lines).strip()
            suggestion = " ".join(suggestion_lines).strip()
            if not suggestion:
                suggestion = "Review the CI/CD log finding above and apply the recommended fix."
                
            if message:
                findings.append(Finding(
                    rule_id=rule_id,
                    rule_name="CI/CD Log Analysis",
                    category=category,
                    severity=severity,
                    confidence=0.99,
                    file_path=file_path,
                    line_number=line_number,
                    code_snippet="N/A",
                    message=message,
                    suggestion=suggestion,
                    source="ai"
                ))
                
        logger.info("   🔍 [CIAgent] Successfully parsed %d findings from CI logs.", len(findings))
        return findings
        
    except Exception as exc:
        logger.error("   ❌ [CIAgent] LLM Call Failed: %s", exc, exc_info=True)
        return [Finding(
            rule_id="CI-FAIL-001",
            rule_name="Continuous Integration Failure",
            category="ci_failure",
            severity="critical",
            confidence=0.0,
            file_path="GitHub Actions",
            line_number=1,
            code_snippet="N/A",
            message="The CI/CD pipeline finished, but the AI log analyzer failed to parse the output.",
            suggestion="Check GitHub Actions manually.",
            source="ai"
        )]

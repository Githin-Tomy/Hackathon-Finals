"""
Summary agent — generates a human-readable PR risk summary.
Provider-agnostic via LangChain (OpenAI or Google Gemini).
"""
from __future__ import annotations
import logging
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from ai.llm import get_llm
from analysis.rules.base import Finding

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior engineering lead writing an executive summary of a pull request code review.
You will be given a list of findings, each with rule_id, severity, category, message, and file_path.

Write a concise Markdown summary (3-5 sentences) covering:
1. Overall risk level (Critical / High / Medium / Low) and why
2. The most important issues to fix before merging
3. Any positive observations (if applicable)

Keep the tone professional and constructive. Use bullet points for the top issues.
Do not repeat the raw finding data verbatim — synthesise it."""


def run_summary_agent(findings: List[Finding], risk_score: float, ci_cd_results: List[dict] = None, historical_comments: List[str] = None) -> str:
    """
    Generate a PR summary from all findings (both rule-based and AI).
    Incorporates CI/CD results and historical comments for deeper context.
    Returns a Markdown string.
    """
    ci_cd_results = ci_cd_results or []
    historical_comments = historical_comments or []

    if not findings and not ci_cd_results and not historical_comments:
        logger.info("   📝 [SummaryAgent] 0 findings and no extra context — skipping LLM call.")
        return "✅ No significant issues found. This PR looks clean!"

    logger.info("   📝 [SummaryAgent] Calling LLM to synthesize executive summary for %d finding(s)...", len(findings))

    findings_data = "\n".join(
        f"- [{f.severity.upper()}] {f.rule_id}: {f.message} ({f.file_path}:{f.line_number})"
        for f in findings
    )
    
    ci_cd_data = "No CI/CD checks found."
    if ci_cd_results:
        ci_cd_data = "\n".join(f"- {c['name']}: {c['status']} ({c['conclusion']})" for c in ci_cd_results)
        
    history_data = "No historical comments found."
    if historical_comments:
        history_data = "\n".join(f"- {hc}" for hc in historical_comments)

    user_prompt = (
        f"**Risk score: {risk_score}/10**\n\n"
        f"**Findings ({len(findings)} total):**\n{findings_data}\n\n"
        f"**CI/CD Pipeline Status:**\n{ci_cd_data}\n\n"
        f"**Historical Review Context:**\n{history_data}"
    )

    try:
        llm = get_llm()
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
        response = llm.invoke(messages)
        summary = response.content or "Summary unavailable."
        logger.info("   📝 [SummaryAgent] Executive summary generated successfully.")
        return summary
    except Exception as exc:
        logger.error("   ❌ [SummaryAgent] LLM Call Failed: %s", exc, exc_info=True)
        return (
            f"⚠️ Summary generation failed. "
            f"Risk score: {risk_score}/10. Total findings: {len(findings)}."
        )

"""
Code review specialist agent — provider-agnostic via LangChain.
Works with OpenAI (gpt-4o, gpt-3.5-turbo) and Google Gemini.
"""
from __future__ import annotations
import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from ai.llm import run_llm_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert senior software engineer performing a code review.
You will be given a JSON object containing:
- "modified_files": a list of file paths that were directly changed in the Pull Request.
- "code_context": a dictionary of {file_path: full_source_code} containing all modified files and their downstream caller files. Note: In "code_context", each line of code is prefixed with its 1-indexed line number (e.g., "12: def foo():"). Use these exact line numbers to identify the correct "line_number" for your findings.
- "architecture_context": structural details, caller signatures, and initial design flows retrieved from Chroma DB for the modified files.

Your job is to:
1. Scan the "modified_files" for any code quality issues, bugs, logical flaws, performance bottlenecks, or poor naming conventions.
2. Compare the proposed changes against the "architecture_context" (if provided) to detect if the logic violates the initial design patterns or core workflows of the repository (e.g. bypassing controller layers, modifying core additive algorithms to subtraction, breaking class signatures).
3. If an architectural deviation or core workflow deviation is detected, output a finding with "rule_id": "CS-ARCH-DEV", "severity": "high" or "critical", and describe the deviation in detail.
4. Use the "code_context" to check if the changes break any upstream or downstream caller functions.
5. For each issue you find, produce a structured analysis.

Respond ONLY with a valid JSON object with a key "results" containing an array. Each element must have:
{
  "rule_id": "CS-GEN-001" or "CS-ARCH-DEV",
  "file_path": "<file path where the issue exists>",
  "line_number": <exact line number where the issue starts>,
  "severity": "critical|high|medium|low",
  "confidence": <float 0.0-1.0>,
  "analysis": "<2-3 sentence explanation of the issue and why it should be fixed or why it deviates from initial design>",
  "suggestion": "<concrete fix recommendation>"
}

Do not include any text outside the JSON object. If you find no code quality or design issues, return {"results": []}."""


def run_code_review_agent(context_json: str) -> list[dict[str, Any]]:
    """
    Call the active LLM to analyse code smell findings.
    Returns a list of enriched finding dicts.
    """
    return run_llm_agent(SYSTEM_PROMPT, context_json, "🛠️ [CodeReviewAgent]")

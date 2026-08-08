"""
Code review specialist agent — provider-agnostic via LangChain.
Works with OpenAI (gpt-4o, gpt-3.5-turbo) and Google Gemini.
"""
from __future__ import annotations
import json
import logging
from typing import Any

from ai.llm import run_llm_agent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert senior software engineer performing an architectural and code quality review.
You will be given a JSON object containing:
- "modified_files": a list of file paths that were directly changed in the Pull Request.
- "code_context": a dictionary of {file_path: full_source_code} containing all modified files and their downstream caller files with 1-indexed line numbers (e.g., "12: def foo():"). Use these exact line numbers.
- "architecture_context": baseline structural details, caller signatures, and design patterns from Chroma DB for the repository.

CRITICAL REQUIREMENT FOR CORE WORKFLOW / ARCHITECTURAL DEVIATION:
Scan the code for ANY core workflow deviations or architectural pattern violations, such as:
1. Modifying core business logic or algorithms (e.g. changing addition to subtraction, altering financial calculations, or changing validation logic).
2. Bypassing controller/service layers, breaking API method contracts, or altering expected return structures.
3. Swallowing exceptions, introducing unexpected side effects, or breaking assumptions of caller functions.

If ANY core workflow deviation or architectural pattern violation is detected:
- You MUST set "rule_id": "CS-ARCH-DEV"
- You MUST set "severity": "critical" or "high"
- You MUST set "category": "architecture"
- In "analysis", clearly describe the deviation (e.g., "Core workflow deviation detected: Algorithm modified from addition to subtraction in validation logic.").

Respond ONLY with a valid JSON object with a key "results" containing an array of objects:
{
  "rule_id": "CS-ARCH-DEV" or "CS-GEN-001",
  "category": "architecture" or "code_smell",
  "file_path": "<file path where the issue exists>",
  "line_number": <exact 1-indexed line number>,
  "severity": "critical|high|medium|low",
  "confidence": <float 0.0-1.0>,
  "analysis": "<detailed explanation of the code smell or core workflow deviation>",
  "suggestion": "<concrete fix recommendation>"
}

Do not include any text outside the JSON object. If you find no code quality or design issues, return {"results": []}."""


def run_code_review_agent(context_json: str) -> list[dict[str, Any]]:
    """
    Call the active LLM to analyse code smell and core workflow deviation findings.
    Returns a list of enriched finding dicts.
    """
    return run_llm_agent(SYSTEM_PROMPT, context_json, "🛠️ [CodeReviewAgent]")

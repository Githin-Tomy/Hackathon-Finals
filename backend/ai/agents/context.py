"""
Context compression and privacy redaction before sending to the LLM.
"""
from __future__ import annotations
import json
import re
from typing import List

from analysis.rules.base import Finding

# ── Redaction patterns ────────────────────────────────────────────────────────
_REDACT_PATTERNS = [
    # API keys / tokens (generic)
    (re.compile(r'(?i)(api[_-]?key|token|secret|password|passwd)\s*=\s*["\'][^"\']{4,}["\']'),
     lambda m: m.group(0)[:m.group(0).index("=") + 2] + '"***REDACTED***"'),
    # AWS keys
    (re.compile(r'AKIA[0-9A-Z]{16}'), lambda m: "***AWS_KEY***"),
    # OpenAI keys
    (re.compile(r'sk-[a-zA-Z0-9]{20,}'), lambda m: "***OPENAI_KEY***"),
    # E-mail addresses
    (re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'), lambda m: "***EMAIL***"),
    # IPv4 addresses
    (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), lambda m: "***IP***"),
]


def redact(text: str) -> str:
    """Apply all redaction patterns to a code snippet or source string."""
    for pattern, replacer in _REDACT_PATTERNS:
        text = pattern.sub(replacer, text)
    return text


# ── Context compression ───────────────────────────────────────────────────────

def build_context(
    findings: List[Finding],
    file_contents: dict[str, str],
    max_snippet_lines: int = 15,
) -> str:
    """
    Build a compact JSON context string for the AI agents.

    Structure:
    {
      "findings": [...],
      "code_context": { "file_path": "...lines around finding..." }
    }
    """
    code_context: dict[str, str] = {}

    for f in findings:
        if f.file_path in file_contents:
            lines = file_contents[f.file_path].splitlines()
            start = max(0, f.line_number - 5)
            end = min(len(lines), f.line_number + max_snippet_lines)
            snippet = "\n".join(
                f"{i + 1:4d} | {redact(lines[i])}"
                for i in range(start, end)
            )
            key = f"{f.file_path}:{f.line_number}"
            code_context[key] = snippet

    payload = {
        "findings": [
            {
                "rule_id": f.rule_id,
                "rule_name": f.rule_name,
                "category": f.category,
                "severity": f.severity,
                "confidence": f.confidence,
                "file_path": f.file_path,
                "line_number": f.line_number,
                "code_snippet": redact(f.code_snippet),
                "message": f.message,
            }
            for f in findings
        ],
        "code_context": code_context,
    }
    return json.dumps(payload, indent=2)

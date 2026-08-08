"""
OpenAI / Custom GPT model factory using ChatOpenAI and httpx with SSL verification disabled.
"""
from __future__ import annotations
import json
import logging
import httpx
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)


# Singleton httpx client to avoid connection leaks across agent calls.
# verify=False is needed for internal genailab endpoints with self-signed certs.
_http_client = httpx.Client(verify=False)


def get_llm() -> ChatOpenAI:
    """
    Returns a ChatOpenAI client initialized with custom base_url, model,
    api_key from .env and an unverified httpx client for custom endpoints.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not configured in your .env file.")

    return ChatOpenAI(
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=settings.openai_temperature,
        http_client=_http_client,
    )


def run_llm_agent(system_prompt: str, context_json: str, label: str) -> list[dict[str, Any]]:
    """
    Shared execution loop for LangGraph specialist agents.
    Calls the LLM, handles errors, and robustly parses the JSON array response.
    """
    logger.info("   %s Calling LLM to analyze findings...", label)
    try:
        llm = get_llm()
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context_json),
        ]
        response = llm.invoke(messages)
        raw = response.content or "{}"

        # Strip markdown code fences if model wraps in ```json
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        parsed = json.loads(raw)
        results = []
        if isinstance(parsed, list):
            results = parsed
        elif isinstance(parsed, dict):
            for key in ("results", "findings", "items", "analysis"):
                if key in parsed and isinstance(parsed[key], list):
                    results = parsed[key]
                    break

        logger.info("   %s LLM analysis completed successfully (%d finding(s) evaluated).", label, len(results))
        return results
    except Exception as exc:
        logger.error("   ❌ %s LLM Call Failed: %s", label, exc, exc_info=True)
        return []

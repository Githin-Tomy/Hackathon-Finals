"""
Model settings API — returns active model configuration.
"""
from __future__ import annotations
from fastapi import APIRouter
from app.config import get_settings

router = APIRouter()


@router.get("/model")
def get_model_config():
    """Return active LLM model configuration from environment."""
    s = get_settings()
    return {
        "model": s.openai_model,
        "base_url": s.openai_base_url,
    }

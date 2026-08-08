import os
# ── Offline tiktoken cache — must be set BEFORE any langchain/openai imports ──
# Prevents SSL certificate errors when tiktoken tries to download cl100k_base.tiktoken
os.environ.setdefault("TIKTOKEN_CACHE_DIR", r"C:\Users\GenAIKOCVISUSR62\tiktoken_cache")
os.environ.setdefault("PYTHONHTTPSVERIFY", "0")

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import create_tables
from app.routers import webhook, reviews, eval as eval_router, settings as settings_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup."""
    logger.info("Starting up — creating database tables…")
    create_tables()
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="AI Code Review Platform",
    description=(
        "Multi-agent AI code review system using LangGraph + OpenAI. "
        "Hybrid rule-based AST analysis + LLM specialist agents for "
        "security and code-quality findings."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS (allow all for hackathon dev) ──────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(webhook.router,         prefix="/webhook",      tags=["Webhook"])
app.include_router(reviews.router,         prefix="/api",          tags=["Reviews"])
app.include_router(eval_router.router,     prefix="/api/eval",     tags=["Eval"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])


@app.get("/health")
def health_check():
    """Liveness check — returns active model config and auth mode."""
    github_auth = "github_app (bot)" if settings.use_github_app else "personal_token"
    return {
        "status": "ok",
        "version": "2.0.0",
        "active_model": settings.openai_model,
        "base_url": settings.openai_base_url,
        "github_auth": github_auth,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.app_port, reload=True)

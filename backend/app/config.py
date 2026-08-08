from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── GitHub PAT (fallback / simple mode) ─────────────────────────────────
    # Used if GitHub App credentials are not set
    github_token: str = ""
    github_webhook_secret: str = "your-webhook-secret"

    # ── GitHub App (bot identity — recommended) ──────────────────────────────
    # Create a GitHub App at https://github.com/settings/apps/new
    # Comments will appear as "your-app-name[bot]" instead of your username
    github_app_id: str = ""            # e.g. "123456"
    github_app_private_key: str = ""   # Full PEM content (multiline, use \n)
    github_app_installation_id: str = ""  # Found in: Settings → Integrations → GitHub Apps

    # ── OpenAI / Custom GPT LLM ─────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-3.5-turbo"
    openai_base_url: str = "https://genailab.tcs.in"
    openai_temperature: float = 0.1
    context_sync_model: str = "azure/genailab-maas-gpt-4.1-nano"
    embedding_model: str = "azure/genailab-maas-text-embedding-3-large"

    # ── App ─────────────────────────────────────────────────────────────────
    database_url: str = "sqlite:///./code_review.db"
    confidence_threshold: float = 0.95
    app_port: int = 8000
    environment: str = "development"

    @property
    def use_github_app(self) -> bool:
        """True if GitHub App credentials (App ID and Private Key) are set."""
        return bool(self.github_app_id and self.github_app_private_key)

    class Config:
        env_file = ("../.env", ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

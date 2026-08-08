"""
GitHub client factory.

Auth priority:
  1. GitHub App (bot identity — posts as "your-app-name[bot]")
  2. Personal Access Token fallback (posts as your personal account)

The client is cached module-level to avoid re-authenticating on every API call.
"""
from __future__ import annotations
import logging

import urllib3
from github import Auth, Github, GithubIntegration

from app.config import get_settings

# Suppress SSL verification warnings from PyGitHub (enterprise endpoint)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Module-level client cache — reset to None to force re-auth
_client: Github | None = None


def get_github_client() -> Github:
    """
    Return an authenticated Github client (cached per process).

    Uses GitHub App auth when GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY are set,
    auto-discovering the Installation ID from the API if not explicitly provided.
    Falls back to PAT if App auth is unavailable.
    """
    global _client
    if _client is not None:
        return _client

    settings = get_settings()

    if settings.use_github_app:
        try:
            # Normalise PEM key — .env may store newlines as literal \n
            private_key = (
                settings.github_app_private_key
                .strip("'\"")
                .replace("\\n", "\n")
                .strip()
            )
            if not private_key.startswith("-----BEGIN"):
                private_key = (
                    f"-----BEGIN RSA PRIVATE KEY-----\n"
                    f"{private_key}\n"
                    f"-----END RSA PRIVATE KEY-----"
                )

            app_id = str(settings.github_app_id).strip()
            installation_id = settings.github_app_installation_id

            # Auto-discover installation ID if not provided in .env
            if not installation_id:
                try:
                    integration = GithubIntegration(app_id, private_key, verify=False)
                    installations = list(integration.get_installations())
                    if installations:
                        installation_id = str(installations[0].id)
                        logger.info("Auto-discovered GitHub App Installation ID: %s", installation_id)
                    else:
                        logger.warning(
                            "GitHub App (%s) is not installed on any repository. "
                            "Install it at: GitHub Settings → Developer Settings → GitHub Apps → Install App.",
                            app_id,
                        )
                except Exception as exc:
                    logger.warning("Could not auto-discover GitHub App installations: %s", exc)

            if installation_id:
                logger.info("Using GitHub App authentication (bot identity)")
                auth = Auth.AppInstallationAuth(
                    Auth.AppAuth(app_id, private_key),
                    int(installation_id),
                )
                _client = Github(auth=auth, verify=False)
                return _client

        except Exception as exc:
            logger.warning("GitHub App auth failed (%s) — falling back to PAT.", exc)

    # PAT fallback
    if settings.github_token:
        logger.info("Using Personal Access Token authentication")
        _client = Github(auth=Auth.Token(settings.github_token), verify=False)
        return _client

    raise ValueError(
        "No GitHub credentials configured. "
        "Set GITHUB_TOKEN (PAT) or GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY in .env."
    )


def get_repo(full_name: str):
    """Return a PyGitHub Repository object by full name (e.g. 'owner/repo')."""
    return get_github_client().get_repo(full_name)


def get_pull_request(full_name: str, pr_number: int):
    """Return a PyGitHub PullRequest object."""
    return get_repo(full_name).get_pull(pr_number)

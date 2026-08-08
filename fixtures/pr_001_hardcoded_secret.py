"""
Fixture: pr_001_hardcoded_secret
Injected issue: API_KEY hardcoded in source → SEC001 Critical
Expected finding: SEC001 (confidence ≥ 95% → direct publish)
"""
import requests

# ❌ BAD: Hardcoded API key — should use os.environ instead
API_KEY = "sk-live-abc123XYZsupersecrettoken9876"
BASE_URL = "https://api.example.com/v2"


def fetch_user_data(user_id: int) -> dict:
    """Fetch user profile from the API."""
    headers = {"Authorization": f"Bearer {API_KEY}"}
    response = requests.get(f"{BASE_URL}/users/{user_id}", headers=headers)
    response.raise_for_status()
    return response.json()


def update_user(user_id: int, data: dict) -> dict:
    """Update a user's profile."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.put(f"{BASE_URL}/users/{user_id}", json=data, headers=headers)
    response.raise_for_status()
    return response.json()

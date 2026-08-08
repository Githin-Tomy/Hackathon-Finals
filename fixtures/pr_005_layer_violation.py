"""
Fixture: pr_005_layer_violation
Injected issue: Controller importing directly from the database layer → Architecture finding
Also has an unused import → CS004
Expected findings: CS004 (unused import)
"""
# ❌ BAD: Controller importing directly from DB layer — violates layered architecture
# Controllers should only talk to service/use-case layer, never directly to DB models
import sqlite3
import json
import os   # ❌ unused import — CS004

from typing import List, Optional
from fastapi import APIRouter, HTTPException

router = APIRouter()


# ❌ BAD: Raw SQL inside a controller — business logic leaked into the API layer
def _fetch_user_from_db(user_id: int) -> Optional[dict]:
    """Direct database access from controller — should be in a repository/service."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, role FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "username": row[1], "email": row[2], "role": row[3]}


@router.get("/users/{user_id}")
def get_user(user_id: int):
    """
    ❌ BAD: This controller:
    1. Imports sqlite3 (should import a UserRepository/UserService)
    2. Contains raw SQL (business logic in the wrong layer)
    3. Has no caching, no retry logic — concerns that belong in a service layer
    """
    user = _fetch_user_from_db(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users")
def list_users():
    """List all users — again hitting DB directly from controller."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email FROM users LIMIT 100")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "email": r[2]} for r in rows]

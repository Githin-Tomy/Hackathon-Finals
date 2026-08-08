"""
Fixture: pr_002_sql_injection
Injected issue: SQL query built with f-string → SEC003 Critical
Expected finding: SEC003 (confidence ≥ 95% → direct publish)
"""
import sqlite3


def get_user_by_username(username: str) -> dict | None:
    """Retrieve a user record by username."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    query = f"SELECT * FROM users WHERE username = '{username}'"
    cursor.execute(query)
    row = cursor.fetchone()
    conn.close()

    if row:
        return {"id": row[0], "username": row[1], "email": row[2]}
    return None


def delete_user(user_id: str) -> bool:
    """Delete a user by ID."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    # ❌ BAD: string concatenation in SQL
    sql = "DELETE FROM users WHERE id = " + user_id
    cursor.execute(sql)
    conn.commit()
    conn.close()
    return cursor.rowcount > 0


def search_products(search_term: str) -> list:
    """Search products by name."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()

    # ✅ GOOD: parameterised query (for comparison)
    cursor.execute("SELECT * FROM products WHERE name LIKE ?", (f"%{search_term}%",))
    return cursor.fetchall()

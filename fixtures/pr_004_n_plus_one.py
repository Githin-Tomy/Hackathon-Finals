"""
Fixture: pr_004_n_plus_one
Injected issue: DB call inside a loop (N+1 query pattern) → Performance finding
Expected finding: CS001 (the wrapper function is also long)
The N+1 pattern itself is < 95% confidence → AI review path
"""
import sqlite3
from typing import List


def get_all_users() -> List[dict]:
    """Fetch all users from the database."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1]} for r in rows]


def get_user_orders(user_id: int) -> List[dict]:
    """Fetch orders for a specific user."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    # ✅ Parameterised — no SQL injection here
    cursor.execute("SELECT id, total FROM orders WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "total": r[1]} for r in rows]


def build_user_report() -> List[dict]:
    """
    ❌ BAD: N+1 query pattern.
    Fetches all users, then makes a separate DB call for each user's orders.
    With 1000 users this makes 1001 queries. Should use a JOIN or bulk fetch.
    """
    users = get_all_users()
    report = []
    for user in users:
        # ❌ DB call inside loop — N+1 problem
        orders = get_user_orders(user["id"])
        order_total = sum(o["total"] for o in orders)
        report.append({
            "user_id": user["id"],
            "username": user["username"],
            "order_count": len(orders),
            "total_spent": order_total,
        })
    return report


def get_product_details(product_id: int) -> dict:
    """Fetch product details by ID."""
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {}
    return {"id": row[0], "name": row[1], "price": row[2], "stock": row[3]}


def enrich_cart_items(cart: List[dict]) -> List[dict]:
    """
    ❌ BAD: Another N+1 — fetches product details one by one inside a loop.
    Should batch-fetch all product_ids in a single IN query.
    """
    enriched = []
    for item in cart:
        # DB call inside loop
        product = get_product_details(item["product_id"])
        enriched.append({**item, "product_name": product.get("name"), "price": product.get("price")})
    return enriched

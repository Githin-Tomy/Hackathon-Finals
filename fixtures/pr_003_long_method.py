"""
Fixture: pr_003_long_method
Injected issue: 80-line method with cyclomatic complexity ~18 → CS001 Medium
Expected finding: CS001 (confidence 0.90 < 0.95 → AI review path)
"""
import re
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def process_order(
    order_id: str,
    user: dict,
    cart: list,
    payment_info: dict,
    shipping_address: dict,
    promo_code: str = "",
) -> dict:
    """
    Process a customer order end-to-end.
    ❌ BAD: This method is far too long and does too many things.
    It should be decomposed into validate_cart(), apply_promo(),
    charge_payment(), create_shipment(), etc.
    """
    # Step 1: Validate user
    if not user:
        return {"success": False, "error": "No user provided"}
    if not user.get("id"):
        return {"success": False, "error": "User has no ID"}
    if not user.get("email"):
        return {"success": False, "error": "User has no email"}

    # Step 2: Validate cart
    if not cart:
        return {"success": False, "error": "Cart is empty"}
    total = 0.0
    for item in cart:
        if not item.get("sku"):
            return {"success": False, "error": f"Item missing SKU: {item}"}
        if item.get("quantity", 0) <= 0:
            return {"success": False, "error": f"Invalid quantity for SKU {item['sku']}"}
        if item.get("price", 0) <= 0:
            return {"success": False, "error": f"Invalid price for SKU {item['sku']}"}
        total += item["price"] * item["quantity"]

    # Step 3: Apply promo code
    discount = 0.0
    if promo_code:
        promo_code = promo_code.strip().upper()
        if promo_code == "SAVE10":
            discount = total * 0.10
        elif promo_code == "SAVE20":
            discount = total * 0.20
        elif promo_code == "FREESHIP":
            discount = 5.99
        else:
            logger.warning("Unknown promo code: %s", promo_code)
    total -= discount

    # Step 4: Validate payment
    if not payment_info:
        return {"success": False, "error": "No payment info"}
    card_number = payment_info.get("card_number", "")
    if not re.match(r"^\d{16}$", card_number):
        return {"success": False, "error": "Invalid card number format"}
    expiry = payment_info.get("expiry", "")
    if not re.match(r"^\d{2}/\d{2}$", expiry):
        return {"success": False, "error": "Invalid expiry format (MM/YY)"}
    cvv = payment_info.get("cvv", "")
    if not re.match(r"^\d{3,4}$", cvv):
        return {"success": False, "error": "Invalid CVV"}

    # Step 5: Validate shipping address
    if not shipping_address:
        return {"success": False, "error": "No shipping address"}
    for field in ("street", "city", "postal_code", "country"):
        if not shipping_address.get(field):
            return {"success": False, "error": f"Shipping address missing: {field}"}

    # Step 6: Charge payment (stubbed)
    charge_result = {"success": True, "transaction_id": f"TXN-{order_id}-001"}
    if not charge_result["success"]:
        return {"success": False, "error": "Payment declined"}

    # Step 7: Create order record (stubbed)
    order = {
        "order_id": order_id,
        "user_id": user["id"],
        "items": cart,
        "subtotal": total + discount,
        "discount": discount,
        "total": total,
        "status": "confirmed",
        "transaction_id": charge_result["transaction_id"],
    }

    # Step 8: Send confirmation email (stubbed)
    logger.info("Order %s confirmed for user %s — total: %.2f", order_id, user["id"], total)

    return {"success": True, "order": order}

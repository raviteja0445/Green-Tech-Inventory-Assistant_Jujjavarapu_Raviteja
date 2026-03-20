"""
validation.py
Input validation for inventory items and forms.
Returns (is_valid: bool, errors: list[str]).
"""

from datetime import datetime, date
import pandas as pd


def validate_item(item: dict) -> tuple[bool, list[str]]:
    """Validate a new/updated item dict. Returns (ok, list_of_error_messages)."""
    errors = []

    # Item name
    name = item.get("item_name", "").strip()
    if not name:
        errors.append("Item name is required.")

    # Quantity
    qty = item.get("quantity_on_hand")
    if qty is None:
        errors.append("Quantity is required.")
    else:
        try:
            qty = float(qty)
            if qty < 0:
                errors.append("Quantity cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Quantity must be a number.")

    # Expiry date
    exp = item.get("expiry_date")
    if exp is None or (isinstance(exp, str) and exp.strip() == ""):
        errors.append("Expiry date is required.")
    else:
        try:
            if isinstance(exp, str):
                exp_dt = datetime.strptime(exp, "%Y-%m-%d").date()
            elif isinstance(exp, (datetime, date)):
                exp_dt = exp if isinstance(exp, date) else exp.date()
            elif isinstance(exp, pd.Timestamp):
                exp_dt = exp.date()
            else:
                exp_dt = None
                errors.append("Expiry date format is invalid.")

            if exp_dt and exp_dt <= datetime.now().date():
                errors.append("Expiry date must be in the future.")
        except ValueError:
            errors.append("Expiry date format is invalid (expected YYYY-MM-DD).")

    # Category
    cat = item.get("category", "").strip()
    if not cat:
        errors.append("Category is required.")

    # Unit
    unit = item.get("unit", "").strip()
    if not unit:
        errors.append("Unit is required.")

    return (len(errors) == 0, errors)


def validate_usage_log(log: dict) -> tuple[bool, list[str]]:
    """Validate a usage log entry."""
    errors = []
    if not log.get("item_id"):
        errors.append("Item ID is required.")
    qty = log.get("quantity_used")
    if qty is None:
        errors.append("Quantity used is required.")
    else:
        try:
            if float(qty) < 0:
                errors.append("Quantity used cannot be negative.")
        except (ValueError, TypeError):
            errors.append("Quantity used must be a number.")
    return (len(errors) == 0, errors)

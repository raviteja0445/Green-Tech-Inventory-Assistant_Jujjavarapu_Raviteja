"""
reorder_engine.py
Core deterministic decision layer — shared by dashboard AND simulator.
All inventory math lives here. No duplication allowed.
"""

import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ──────────────────── Atomic calculations ────────────────────


def compute_avg_daily_usage(usage_logs: pd.DataFrame, item_id: str, window_days: int = 7) -> float:
    """Rolling average daily usage over the last `window_days` days."""
    today = pd.Timestamp(datetime.now().date())
    cutoff = today - pd.Timedelta(days=window_days)
    logs = usage_logs[(usage_logs["item_id"] == item_id) & (usage_logs["date"] >= cutoff)]
    if logs.empty or window_days <= 0:
        return 0.0
    return logs["quantity_used"].sum() / window_days


def compute_weekday_weekend_avg(usage_logs: pd.DataFrame, item_id: str, window_days: int = 14) -> dict:
    """Return separate weekday and weekend averages for insight generation."""
    today = pd.Timestamp(datetime.now().date())
    cutoff = today - pd.Timedelta(days=window_days)
    logs = usage_logs[(usage_logs["item_id"] == item_id) & (usage_logs["date"] >= cutoff)].copy()
    if logs.empty:
        return {"weekday_avg": 0.0, "weekend_avg": 0.0}
    logs["dow"] = logs["date"].dt.dayofweek  # 0=Mon, 6=Sun
    weekday = logs[logs["dow"] < 5]
    weekend = logs[logs["dow"] >= 5]
    n_weekdays = max(1, len(weekday["date"].dt.date.unique()))
    n_weekends = max(1, len(weekend["date"].dt.date.unique()))
    return {
        "weekday_avg": weekday["quantity_used"].sum() / n_weekdays if not weekday.empty else 0.0,
        "weekend_avg": weekend["quantity_used"].sum() / n_weekends if not weekend.empty else 0.0,
    }


def compute_days_remaining(current_stock: float, avg_daily_usage: float) -> float:
    """How many days the current stock will last."""
    if avg_daily_usage <= 0:
        return float("inf")
    return current_stock / avg_daily_usage


def compute_days_until_expiry(expiry_date, today: datetime = None) -> int:
    """Calendar days until the item expires. Negative if already expired."""
    if today is None:
        today = datetime.now().date()
    if isinstance(expiry_date, pd.Timestamp):
        expiry_date = expiry_date.date()
    if isinstance(today, datetime):
        today = today.date()
    return (expiry_date - today).days


def compute_projected_usage_before_expiry(avg_daily_usage: float, days_until_expiry: int) -> float:
    """How much stock is likely to be consumed before expiry."""
    if days_until_expiry <= 0:
        return 0.0
    return avg_daily_usage * days_until_expiry


def compute_waste_risk(current_stock: float, projected_usage_before_expiry: float) -> str:
    """Classify waste risk as high / medium / low."""
    if projected_usage_before_expiry <= 0 and current_stock > 0:
        return "high"
    if current_stock <= 0:
        return "low"
    ratio = current_stock / max(projected_usage_before_expiry, 0.01)
    if ratio > 1.3:
        return "high"
    elif ratio > 1.0:
        return "medium"
    return "low"


# ──────────────────── Reorder decision ────────────────────


def compute_reorder_decision(
    days_remaining: float,
    lead_time: int,
    days_until_expiry: int,
    current_stock: float,
    avg_daily_usage: float,
    safety_buffer_days: int = 2,
) -> str:
    """
    Returns one of: 'reorder_now', 'reorder_later', 'do_not_reorder'.
    """
    # Already expired
    if days_until_expiry <= 0:
        return "do_not_reorder"

    # No meaningful usage – safe default
    if avg_daily_usage <= 0:
        return "do_not_reorder"

    # Stock covers less than lead-time → reorder now
    if days_remaining <= lead_time:
        return "reorder_now"

    # Stock covers lead-time but not lead-time + safety buffer → reorder later
    if days_remaining <= lead_time + safety_buffer_days:
        return "reorder_later"

    return "do_not_reorder"


def compute_suggested_quantity(
    avg_daily_usage: float,
    lead_time: int,
    current_stock: float,
    safety_buffer_days: int = 2,
    days_until_expiry: int = None,
    is_perishable: bool = False,
) -> float:
    """
    Target stock = avg_daily_usage × (lead_time + safety_buffer).
    For perishables, cap so we don't recommend oversupply that will expire.
    """
    target = avg_daily_usage * (lead_time + safety_buffer_days)
    qty = max(0, target - current_stock)

    # Perishable cap: don't suggest more than can be consumed before expiry
    if is_perishable and days_until_expiry is not None and days_until_expiry > 0:
        max_useful = avg_daily_usage * days_until_expiry
        cap = max(0, max_useful - current_stock)
        qty = min(qty, cap)

    return round(qty, 1)


# ──────────────────── Master analysis (one item) ────────────────────

PERISHABLE_CATEGORIES = {"Dairy", "Produce", "Beverages"}


def analyze_item(
    item: dict,
    usage_logs: pd.DataFrame,
    lead_time: int,
    safety_buffer_days: int = 2,
    today: datetime = None,
) -> dict:
    """
    Full deterministic analysis for a single item.
    Returns a dict of all computed signals — used by dashboard AND simulator.
    """
    if today is None:
        today = datetime.now()

    item_id = item["item_id"]
    current_stock = float(item["quantity_on_hand"])
    expiry_date = item["expiry_date"]
    category = item.get("category", "")

    avg_daily = compute_avg_daily_usage(usage_logs, item_id)
    days_rem = compute_days_remaining(current_stock, avg_daily)
    days_exp = compute_days_until_expiry(expiry_date, today)
    proj_usage = compute_projected_usage_before_expiry(avg_daily, days_exp)
    waste = compute_waste_risk(current_stock, proj_usage)

    is_perishable = category in PERISHABLE_CATEGORIES

    decision = compute_reorder_decision(
        days_rem, lead_time, days_exp, current_stock, avg_daily, safety_buffer_days
    )
    suggested_qty = compute_suggested_quantity(
        avg_daily, lead_time, current_stock, safety_buffer_days, days_exp, is_perishable
    )

    result = {
        "item_id": item_id,
        "item_name": item.get("item_name", item_id),
        "category": category,
        "unit": item.get("unit", "units"),
        "current_stock": current_stock,
        "avg_daily_usage": round(avg_daily, 2),
        "days_remaining": round(days_rem, 1) if days_rem != float("inf") else None,
        "days_until_expiry": days_exp,
        "projected_usage_before_expiry": round(proj_usage, 1),
        "waste_risk": waste,
        "reorder_decision": decision,
        "suggested_reorder_qty": suggested_qty,
        "lead_time": lead_time,
        "is_perishable": is_perishable,
    }

    logger.debug(
        "Item=%s  avg_usage=%.2f  days_rem=%.1f  decision=%s  suggested_qty=%.1f  waste=%s",
        item_id, avg_daily, days_rem if days_rem != float("inf") else -1,
        decision, suggested_qty, waste,
    )

    return result


def analyze_all_items(items_df: pd.DataFrame, usage_logs: pd.DataFrame, suppliers_df: pd.DataFrame, safety_buffer_days: int = 2) -> list[dict]:
    """Run analyze_item for every row and return list of result dicts."""
    merged = items_df.merge(suppliers_df[["supplier_id", "avg_lead_days"]], on="supplier_id", how="left")
    merged["avg_lead_days"] = merged["avg_lead_days"].fillna(3).astype(int)
    results = []
    for _, row in merged.iterrows():
        r = analyze_item(
            row.to_dict(),
            usage_logs,
            lead_time=int(row["avg_lead_days"]),
            safety_buffer_days=safety_buffer_days,
        )
        results.append(r)
    return results

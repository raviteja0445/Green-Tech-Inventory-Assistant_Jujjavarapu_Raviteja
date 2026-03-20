"""
insights.py
Consumption pattern analysis — returns top 3-5 compact insights.
"""

import pandas as pd
from src.reorder_engine import compute_avg_daily_usage, compute_weekday_weekend_avg


def generate_insights(items_df: pd.DataFrame, usage_logs: pd.DataFrame, analysis_results: list[dict], top_n: int = 5) -> list[dict]:
    """
    Analyze usage patterns and return a compact list of insights.

    Each insight is a dict with:
      - type: str (fast_moving | slow_moving | weekend_spike | stable | overstock_prone)
      - item_name: str
      - message: str
    """
    insights = []

    for r in analysis_results:
        item_id = r["item_id"]
        item_name = r["item_name"]
        avg_daily = r["avg_daily_usage"]
        waste = r["waste_risk"]

        ww = compute_weekday_weekend_avg(usage_logs, item_id)
        weekday_avg = ww["weekday_avg"]
        weekend_avg = ww["weekend_avg"]

        # --- Compute usage variance for stability ---
        recent = usage_logs[usage_logs["item_id"] == item_id].tail(7)
        if len(recent) >= 3:
            cv = recent["quantity_used"].std() / max(recent["quantity_used"].mean(), 0.01)
        else:
            cv = 0.0

        # Fast-moving
        if avg_daily >= 5:
            insights.append({
                "type": "fast_moving",
                "item_name": item_name,
                "message": f"{item_name} is fast-moving at ~{avg_daily:.1f} {r['unit']}/day. Monitor stock closely.",
                "priority": avg_daily,
            })

        # Slow-moving
        elif avg_daily > 0 and avg_daily < 1.5:
            insights.append({
                "type": "slow_moving",
                "item_name": item_name,
                "message": f"{item_name} is slow-moving (~{avg_daily:.1f} {r['unit']}/day). Avoid over-ordering.",
                "priority": 2,
            })

        # Weekend spike
        if weekend_avg > 0 and weekday_avg > 0 and weekend_avg > weekday_avg * 1.15:
            pct = round((weekend_avg / weekday_avg - 1) * 100)
            insights.append({
                "type": "weekend_spike",
                "item_name": item_name,
                "message": f"{item_name} weekend usage is ~{pct}% higher than weekday usage.",
                "priority": pct,
            })

        # Stable demand
        if cv < 0.25 and avg_daily > 0 and len(recent) >= 5:
            insights.append({
                "type": "stable",
                "item_name": item_name,
                "message": f"{item_name} has very stable demand (CV={cv:.2f}). Safe for bulk ordering.",
                "priority": 1,
            })

        # Overstock-prone (high or medium waste risk)
        if waste in ("high", "medium"):
            insights.append({
                "type": "overstock_prone",
                "item_name": item_name,
                "message": f"{item_name} is overstock-prone — current stock exceeds projected consumption before expiry.",
                "priority": 5 if waste == "high" else 3,
            })

    # De-duplicate: keep best per (type, item_name)
    seen = set()
    unique = []
    for ins in insights:
        key = (ins["type"], ins["item_name"])
        if key not in seen:
            seen.add(key)
            unique.append(ins)

    # Sort by priority descending and return top N
    unique.sort(key=lambda x: x.get("priority", 0), reverse=True)
    return unique[:top_n]

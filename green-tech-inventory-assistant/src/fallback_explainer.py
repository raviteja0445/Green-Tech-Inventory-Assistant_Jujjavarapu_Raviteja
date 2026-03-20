"""
fallback_explainer.py
Rule-based explanation generator when AI is unavailable or toggled off.
Produces structured Pattern → Risk → Action sentences from deterministic signals.
"""

from src.reorder_engine import compute_weekday_weekend_avg
import pandas as pd


def generate_fallback_explanation(analysis: dict, usage_logs: pd.DataFrame = None) -> str:
    """
    Build a rule-based explanation from the analysis dict.
    Follows Pattern → Risk → Action structure.
    Always returns a useful string — never "AI unavailable, try again later".
    """
    parts = []

    decision = analysis.get("reorder_decision", "do_not_reorder")
    item_name = analysis.get("item_name", "This item")
    stock = analysis.get("current_stock", 0)
    unit = analysis.get("unit", "units")
    avg_daily = analysis.get("avg_daily_usage", 0)
    days_rem = analysis.get("days_remaining")
    lead_time = analysis.get("lead_time", 3)
    days_exp = analysis.get("days_until_expiry", 999)
    waste = analysis.get("waste_risk", "low")
    suggested_qty = analysis.get("suggested_reorder_qty", 0)
    proj_usage = analysis.get("projected_usage_before_expiry", 0)

    # ---- Pattern → Risk → Action ----
    if decision == "reorder_now":
        parts.append(f"📌 **Pattern**: {item_name} has {stock} {unit} left, burning at ~{avg_daily:.1f} {unit}/day — only ~{days_rem:.0f} days of stock remain.")
        parts.append(f"⚠️ **Risk**: Stockout before resupply. Supplier lead time is {lead_time} days, but stock covers only ~{days_rem:.0f} days.")
        if suggested_qty > 0:
            parts.append(f"✅ **Action**: Reorder **{suggested_qty:.0f} {unit}** immediately to bridge the gap.")
        else:
            parts.append(f"✅ **Action**: Place an emergency reorder now.")
    elif decision == "reorder_later":
        parts.append(f"📌 **Pattern**: {item_name} has {stock} {unit} on hand (~{days_rem:.0f} days remaining at {avg_daily:.1f} {unit}/day).")
        parts.append(f"⚠️ **Risk**: Stock will approach threshold within {lead_time + 2} days. Delay risks a stockout window.")
        parts.append(f"✅ **Action**: Plan a reorder of ~{suggested_qty:.0f} {unit} within the next {max(1, int(days_rem - lead_time))} days.")
    else:
        if days_exp <= 0:
            parts.append(f"📌 **Pattern**: {item_name} has **expired**.")
            parts.append(f"⚠️ **Risk**: Using expired inventory creates liability and waste.")
            parts.append(f"✅ **Action**: Remove {stock} {unit} from active inventory immediately.")
        elif avg_daily <= 0:
            parts.append(f"📌 **Pattern**: {item_name} has {stock} {unit} but zero recorded usage in the last 7 days.")
            parts.append(f"⚠️ **Risk**: Dead stock ties up budget. May expire before use (expires in {days_exp} days).")
            parts.append(f"✅ **Action**: Do not reorder. Review whether this item is still needed.")
        else:
            parts.append(f"📌 **Pattern**: {item_name} has {stock} {unit} — ~{days_rem:.0f} days supply at {avg_daily:.1f} {unit}/day.")
            parts.append(f"⚠️ **Risk**: Low risk. Stock comfortably covers lead time of {lead_time} days.")
            parts.append(f"✅ **Action**: No reorder needed. Next review recommended in ~{max(1, int(days_rem - lead_time))} days.")

    # ---- Waste risk ----
    if waste == "high":
        parts.append(f"🗑️ **Waste Alert**: {stock} {unit} on hand but only ~{proj_usage:.0f} {unit} projected to be used before expiry — risk of {max(0, stock - proj_usage):.0f} {unit} wasted.")
    elif waste == "medium":
        parts.append(f"🗑️ **Waste Alert**: Stock is slightly above projected consumption before expiry. Consider smaller batch orders.")

    # ---- Weekend pattern ----
    if usage_logs is not None:
        ww = compute_weekday_weekend_avg(usage_logs, analysis.get("item_id", ""))
        wd = ww["weekday_avg"]
        we = ww["weekend_avg"]
        if wd > 0 and we > wd * 1.15:
            pct = round((we / wd - 1) * 100)
            parts.append(f"📊 **Weekend Spike**: {item_name} weekend demand is {pct}% higher than weekdays — factor this into reorder timing.")

    return "\n\n".join(parts)


def generate_fallback_insight_summary(insights: list[dict]) -> str:
    """Build a compact rule-based summary from the insight list."""
    if not insights:
        return "No significant consumption pattern insights detected."
    lines = [f"• {i['message']}" for i in insights[:5]]
    return "\n\n".join(lines)

"""
sustainability.py
Simple, credible, count-based sustainability / waste metrics.
No fake carbon science — just countable, interpretable numbers.
"""

import pandas as pd


def compute_sustainability_summary(analysis_results: list[dict], suppliers_df: pd.DataFrame) -> dict:
    """
    Given the list of per-item analysis dicts, compute org-wide sustainability metrics.

    Returns:
        dict with keys:
        - items_avoided_expiry: count of items where stock will likely be consumed before expiry
        - items_at_waste_risk: count of items flagged high/medium waste risk
        - waste_reduction_pct: approx % of items NOT at high waste risk
        - local_supplier_count: count of items sourced from local suppliers
        - refurbished_supplier_count: count sourced from refurbished/eco suppliers
        - good_packaging_count: count with packaging_score >= 4
        - impact_summary: short text summary
    """
    total = len(analysis_results)
    if total == 0:
        return _empty_summary()

    high_waste = sum(1 for r in analysis_results if r["waste_risk"] == "high")
    med_waste = sum(1 for r in analysis_results if r["waste_risk"] == "medium")
    low_waste = sum(1 for r in analysis_results if r["waste_risk"] == "low")

    items_avoided_expiry = low_waste  # items whose stock will be fully consumed before expiry

    waste_reduction_pct = round((1 - high_waste / total) * 100, 1)

    # Supplier sustainability counts
    sup_map = {}
    for _, s in suppliers_df.iterrows():
        sup_map[s["supplier_id"]] = s

    local_count = 0
    refurb_count = 0
    good_pkg_count = 0

    for r in analysis_results:
        sid = None
        # We need item→supplier mapping — look it up from the original data
        # analysis_results don't carry supplier_id, so we accept it as optional
        sid = r.get("supplier_id")
        if sid and sid in sup_map:
            s = sup_map[sid]
            if str(s.get("local_flag", "")).lower() in ("true", "1", "yes"):
                local_count += 1
            if str(s.get("refurbished_flag", "")).lower() in ("true", "1", "yes"):
                refurb_count += 1
            if int(s.get("packaging_score", 0)) >= 4:
                good_pkg_count += 1

    summary_text = (
        f"{items_avoided_expiry} of {total} items on track to be consumed before expiry. "
        f"{high_waste} items have high waste risk. "
        f"Approximate waste avoidance rate: {waste_reduction_pct}%. "
        f"{local_count} items sourced locally. "
        f"{refurb_count} from refurbished/eco suppliers. "
        f"{good_pkg_count} with good packaging scores."
    )

    return {
        "total_items": total,
        "items_avoided_expiry": items_avoided_expiry,
        "items_at_waste_risk": high_waste,
        "items_medium_risk": med_waste,
        "waste_reduction_pct": waste_reduction_pct,
        "local_supplier_count": local_count,
        "refurbished_supplier_count": refurb_count,
        "good_packaging_count": good_pkg_count,
        "impact_summary": summary_text,
    }


def _empty_summary():
    return {
        "total_items": 0,
        "items_avoided_expiry": 0,
        "items_at_waste_risk": 0,
        "items_medium_risk": 0,
        "waste_reduction_pct": 0.0,
        "local_supplier_count": 0,
        "refurbished_supplier_count": 0,
        "good_packaging_count": 0,
        "impact_summary": "No items in inventory yet.",
    }


def compute_sustainability_delta(baseline: dict, scenario: dict) -> dict:
    """
    Compare two results dicts (baseline vs simulated) for delta reporting.
    """
    return {
        "waste_risk_change": f"{baseline.get('waste_risk', 'low')} → {scenario.get('waste_risk', 'low')}",
        "stock_delta": round(scenario.get("current_stock", 0) - baseline.get("current_stock", 0), 1),
        "days_remaining_delta": _safe_delta(scenario.get("days_remaining"), baseline.get("days_remaining")),
    }


def _safe_delta(a, b):
    if a is None or b is None:
        return None
    return round(a - b, 1)

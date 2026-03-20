"""
simulator.py
What-If Purchase Simulator — single-item, 5-7 day projection.
CRITICAL: reuses shared logic from reorder_engine.py — no duplicate formulas.
"""

from datetime import datetime, timedelta
import copy
from src.reorder_engine import (
    analyze_item,
    compute_avg_daily_usage,
    compute_days_until_expiry,
)
from src.sustainability import compute_sustainability_delta
import pandas as pd


def run_simulation(
    item: dict,
    usage_logs: pd.DataFrame,
    lead_time_override: int = None,
    order_quantity: float = 0,
    demand_spike_pct: float = 0,
    smaller_batch: bool = False,
    projection_days: int = 7,
    safety_buffer_days: int = 2,
) -> dict:
    """
    Simulate a what-if scenario for one item.

    Parameters:
        item: dict with item fields (item_id, quantity_on_hand, expiry_date, category, unit, …)
        usage_logs: full usage log DataFrame
        lead_time_override: override supplier lead time (days)
        order_quantity: additional units being ordered
        demand_spike_pct: % increase in daily demand (0-100)
        smaller_batch: if True, halve the order quantity (simulates smaller-batch ordering)
        projection_days: how many days to project (5-7)
        safety_buffer_days: safety buffer for reorder calc

    Returns:
        dict with:
        - daily_projection: list of {day, date, stock, label}
        - stockout_risk: bool
        - waste_risk: str
        - ending_stock: float
        - sustainability_delta: dict
        - scenario_analysis: full analysis dict from shared engine
        - baseline_analysis: full analysis dict from shared engine
    """
    item_id = item["item_id"]
    lead_time = lead_time_override if lead_time_override is not None else int(item.get("avg_lead_days", 3))

    # --- Baseline analysis using shared engine ---
    baseline = analyze_item(item, usage_logs, lead_time=lead_time, safety_buffer_days=safety_buffer_days)

    avg_daily = baseline["avg_daily_usage"]

    # Apply demand spike
    if demand_spike_pct > 0:
        avg_daily = avg_daily * (1 + demand_spike_pct / 100)

    # Apply smaller-batch toggle
    effective_order = order_quantity
    if smaller_batch:
        effective_order = order_quantity / 2.0

    # --- Day-by-day stock projection ---
    today = datetime.now().date()
    current_stock = float(item["quantity_on_hand"])
    expiry_date = item["expiry_date"]
    if isinstance(expiry_date, pd.Timestamp):
        expiry_date = expiry_date.date()
    elif isinstance(expiry_date, str):
        expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d").date()

    daily = []
    stock = current_stock
    stockout_occurred = False
    arrival_day = lead_time  # order arrives after lead_time days

    for d in range(projection_days):
        day_date = today + timedelta(days=d + 1)
        label = ""

        # Deduct daily usage
        stock = stock - avg_daily

        # Order arrives
        if d + 1 == arrival_day and effective_order > 0:
            stock += effective_order
            label = f"+{effective_order:.0f} arrived"

        # Check expiry
        if day_date > expiry_date:
            label += " [EXPIRED]"

        if stock <= 0:
            stockout_occurred = True
            stock = max(stock, 0)

        daily.append({
            "day": d + 1,
            "date": day_date.strftime("%Y-%m-%d"),
            "stock": round(stock, 1),
            "label": label.strip(),
        })

    ending_stock = daily[-1]["stock"] if daily else current_stock

    # --- Scenario analysis using shared engine with modified item ---
    scenario_item = copy.deepcopy(item)
    scenario_item["quantity_on_hand"] = current_stock + effective_order
    scenario = analyze_item(scenario_item, usage_logs, lead_time=lead_time, safety_buffer_days=safety_buffer_days)

    # If demand spike, override the avg usage in the scenario result for display
    if demand_spike_pct > 0:
        scenario["avg_daily_usage"] = round(avg_daily, 2)

    sus_delta = compute_sustainability_delta(baseline, scenario)

    return {
        "daily_projection": daily,
        "stockout_risk": stockout_occurred,
        "waste_risk": scenario["waste_risk"],
        "ending_stock": ending_stock,
        "sustainability_delta": sus_delta,
        "scenario_analysis": scenario,
        "baseline_analysis": baseline,
    }

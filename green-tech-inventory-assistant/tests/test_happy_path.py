"""
test_happy_path.py
Happy-path tests: stable usage, low stock, valid lead time → reorder now.
"""

import sys
import os
import pytest
import pandas as pd
from datetime import datetime, timedelta

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.reorder_engine import (
    compute_avg_daily_usage,
    compute_days_remaining,
    compute_waste_risk,
    compute_reorder_decision,
    compute_suggested_quantity,
    analyze_item,
)
from src.fallback_explainer import generate_fallback_explanation
from src.simulator import run_simulation


def _make_usage_logs(item_id, daily_qty, days=7):
    """Create synthetic usage logs for tests."""
    today = datetime.now().date()
    rows = []
    for d in range(days):
        rows.append({
            "log_id": f"T{d}",
            "item_id": item_id,
            "date": pd.Timestamp(today - timedelta(days=days - d - 1)),
            "quantity_used": daily_qty,
        })
    return pd.DataFrame(rows)


class TestHappyPath:
    """Given stable usage, low stock, and valid lead time → expect reorder now."""

    def test_reorder_now_with_low_stock(self):
        """Item has stable usage of 3/day, only 8 units left, lead time 3 days."""
        usage = _make_usage_logs("ITM001", 3, days=7)
        item = {
            "item_id": "ITM001",
            "item_name": "Coffee Beans",
            "category": "Beverages",
            "quantity_on_hand": 8,
            "unit": "kg",
            "expiry_date": pd.Timestamp("2026-05-15"),
            "reorder_threshold": 15,
            "supplier_id": "SUP001",
        }
        result = analyze_item(item, usage, lead_time=3, safety_buffer_days=2)

        assert result["reorder_decision"] == "reorder_now"
        assert result["suggested_reorder_qty"] > 0
        assert result["avg_daily_usage"] > 0
        assert result["waste_risk"] in ("low", "medium", "high")

    def test_suggested_qty_positive(self):
        """Suggested quantity must be positive when stock < target."""
        qty = compute_suggested_quantity(
            avg_daily_usage=3.0, lead_time=3, current_stock=5,
            safety_buffer_days=2,
        )
        assert qty > 0

    def test_fallback_explanation_available(self):
        """Fallback explanation must produce a non-empty string."""
        analysis = {
            "item_id": "ITM001",
            "item_name": "Coffee Beans",
            "current_stock": 8,
            "unit": "kg",
            "avg_daily_usage": 3.0,
            "days_remaining": 2.7,
            "days_until_expiry": 57,
            "projected_usage_before_expiry": 171.0,
            "waste_risk": "low",
            "reorder_decision": "reorder_now",
            "suggested_reorder_qty": 7,
            "lead_time": 3,
        }
        explanation = generate_fallback_explanation(analysis)
        assert len(explanation) > 20
        assert "REORDER" in explanation.upper()

    def test_days_remaining_calculation(self):
        """Basic days-remaining math."""
        assert compute_days_remaining(10, 2) == 5.0
        assert compute_days_remaining(0, 2) == 0.0

    def test_simulator_consistent_with_engine(self):
        """Simulator baseline analysis must match direct analyze_item output."""
        usage = _make_usage_logs("ITM001", 3, days=7)
        item = {
            "item_id": "ITM001",
            "item_name": "Coffee Beans",
            "category": "Beverages",
            "quantity_on_hand": 8,
            "unit": "kg",
            "expiry_date": pd.Timestamp("2026-05-15"),
            "reorder_threshold": 15,
            "supplier_id": "SUP001",
            "avg_lead_days": 3,
        }
        sim = run_simulation(item, usage, order_quantity=0)
        direct = analyze_item(item, usage, lead_time=3)

        # Baseline from simulator should match direct analysis
        assert sim["baseline_analysis"]["reorder_decision"] == direct["reorder_decision"]
        assert sim["baseline_analysis"]["avg_daily_usage"] == direct["avg_daily_usage"]

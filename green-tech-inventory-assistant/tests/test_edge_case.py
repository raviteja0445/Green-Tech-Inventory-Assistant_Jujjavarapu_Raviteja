"""
test_edge_case.py
Edge-case tests: sparse/zero usage, expired stock, negative quantities,
and boundary conditions. Must never crash.
"""

import sys
import os
import pytest
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.reorder_engine import (
    compute_avg_daily_usage,
    compute_days_remaining,
    compute_waste_risk,
    compute_reorder_decision,
    compute_suggested_quantity,
    compute_projected_usage_before_expiry,
    analyze_item,
)
from src.fallback_explainer import generate_fallback_explanation
from src.validation import validate_item


class TestEdgeCases:

    def test_zero_usage_history(self):
        """No usage logs at all → should not crash, should suggest do_not_reorder."""
        empty_usage = pd.DataFrame(columns=["log_id", "item_id", "date", "quantity_used"])
        empty_usage["date"] = pd.to_datetime(empty_usage["date"])
        item = {
            "item_id": "EDGE01",
            "item_name": "Mystery Item",
            "category": "Other",
            "quantity_on_hand": 50,
            "unit": "units",
            "expiry_date": pd.Timestamp("2026-06-01"),
            "reorder_threshold": 10,
        }
        result = analyze_item(item, empty_usage, lead_time=3)
        assert result["reorder_decision"] == "do_not_reorder"
        assert result["avg_daily_usage"] == 0.0

    def test_expired_item(self):
        """Expired item → do_not_reorder, no crash."""
        empty_usage = pd.DataFrame(columns=["log_id", "item_id", "date", "quantity_used"])
        empty_usage["date"] = pd.to_datetime(empty_usage["date"])
        item = {
            "item_id": "EXP01",
            "item_name": "Expired Milk",
            "category": "Dairy",
            "quantity_on_hand": 10,
            "unit": "units",
            "expiry_date": pd.Timestamp("2025-01-01"),
            "reorder_threshold": 5,
        }
        result = analyze_item(item, empty_usage, lead_time=2)
        assert result["reorder_decision"] == "do_not_reorder"
        assert result["days_until_expiry"] < 0

    def test_expired_item_fallback_explanation(self):
        """Fallback for expired item must mention expiry, not crash."""
        analysis = {
            "item_id": "EXP01",
            "item_name": "Expired Milk",
            "current_stock": 10,
            "unit": "units",
            "avg_daily_usage": 0.0,
            "days_remaining": None,
            "days_until_expiry": -100,
            "projected_usage_before_expiry": 0,
            "waste_risk": "high",
            "reorder_decision": "do_not_reorder",
            "suggested_reorder_qty": 0,
            "lead_time": 2,
        }
        explanation = generate_fallback_explanation(analysis)
        assert "expired" in explanation.lower() or "expir" in explanation.lower()

    def test_days_remaining_zero_usage(self):
        """Zero usage → infinite days remaining."""
        dr = compute_days_remaining(100, 0)
        assert dr == float("inf")

    def test_negative_days_until_expiry(self):
        """Projected usage with negative expiry days → 0."""
        proj = compute_projected_usage_before_expiry(5.0, -3)
        assert proj == 0.0

    def test_validation_missing_name(self):
        """Validation rejects missing item name."""
        ok, errs = validate_item({"item_name": "", "quantity_on_hand": 10,
                                   "expiry_date": "2026-12-31", "category": "Other", "unit": "units"})
        assert not ok
        assert any("name" in e.lower() for e in errs)

    def test_validation_negative_quantity(self):
        """Validation rejects negative quantity."""
        ok, errs = validate_item({"item_name": "Test", "quantity_on_hand": -5,
                                   "expiry_date": "2026-12-31", "category": "Other", "unit": "units"})
        assert not ok
        assert any("negative" in e.lower() for e in errs)

    def test_waste_risk_no_stock(self):
        """Zero stock → low waste risk."""
        assert compute_waste_risk(0, 100) == "low"

    def test_suggested_qty_no_usage(self):
        """Zero usage → suggested qty is 0."""
        qty = compute_suggested_quantity(0, 3, 50)
        assert qty == 0.0

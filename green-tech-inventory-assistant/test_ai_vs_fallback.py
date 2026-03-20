"""Quick diagnostic: compare AI vs Fallback output."""
import os, sys
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
from src.ai_explainer import generate_ai_explanation, _get_model
from src.fallback_explainer import generate_fallback_explanation
import pandas as pd

analysis = {
    "item_id": "ITEM001",
    "item_name": "Coffee Beans",
    "current_stock": 8.0,
    "unit": "kg",
    "avg_daily_usage": 3.0,
    "days_remaining": 2.67,
    "days_until_expiry": 12,
    "waste_risk": "low",
    "reorder_decision": "reorder_now",
    "suggested_reorder_qty": 7,
    "lead_time": 3,
}

print("--- Gemini model init ---")
model = _get_model()
print(f"Model: {model}")

print("\n=== AI EXPLANATION ===")
ai_text, used_ai = generate_ai_explanation(analysis)
print(f"used_ai: {used_ai}")
print(f"text: {ai_text if ai_text else '(empty - AI failed silently)'}")

print("\n=== FALLBACK EXPLANATION ===")
usage_df = pd.DataFrame({
    "item_id": ["ITEM001"],
    "quantity_used": [3.0],
    "date": ["2025-03-18"]
})
fb_text = generate_fallback_explanation(analysis, usage_df)
print(f"text: {fb_text}")

"""
ai_explainer.py
Uses Groq (OpenAI-compatible API) with Llama 3.3 to generate short
natural-language explanations from the structured deterministic signals
produced by reorder_engine.

AI does NOT decide quantities or math — it only explains.
"""

import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

_client = None

GROQ_MODEL = "llama-3.3-70b-versatile"


def _get_client():
    """Lazy-init the Groq client via OpenAI SDK."""
    global _client
    if _client is not None:
        return _client
    try:
        from openai import OpenAI
        import httpx
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key or api_key == "your_api_key_here":
            logger.warning("GROQ_API_KEY not set or is placeholder.")
            return None
        _client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            http_client=httpx.Client(),
        )
        return _client
    except Exception as e:
        logger.warning("Groq client init failed: %s", e)
        return None


def _build_prompt(analysis: dict, insights: list[dict] = None) -> str:
    """Build a concise prompt from structured signals."""
    signals = {
        "item_name": analysis.get("item_name"),
        "current_stock": analysis.get("current_stock"),
        "unit": analysis.get("unit"),
        "avg_daily_usage": analysis.get("avg_daily_usage"),
        "days_remaining": analysis.get("days_remaining"),
        "days_until_expiry": analysis.get("days_until_expiry"),
        "waste_risk": analysis.get("waste_risk"),
        "reorder_decision": analysis.get("reorder_decision"),
        "suggested_reorder_qty": analysis.get("suggested_reorder_qty"),
        "lead_time": analysis.get("lead_time"),
    }

    prompt = (
        "You are a direct inventory advisor for a small organization. "
        "Given the data below, write EXACTLY 3 short bullet points:\n\n"
        "📌 **Pattern**: What the usage data shows (use the actual numbers).\n"
        "⚠️ **Risk**: What happens if nothing is done (stockout in X days, Y units wasted, etc.).\n"
        "✅ **Action**: The specific action to take (reorder X units, reduce order size, etc.).\n\n"
        "Rules: Use real numbers. No filler phrases. 1-2 lines per bullet max.\n\n"
        f"Item Data:\n{json.dumps(signals, indent=2)}\n"
    )

    if insights:
        insight_text = "\n".join(f"- {i['message']}" for i in insights[:3])
        prompt += f"\nConsumption insights:\n{insight_text}\n"

    return prompt


def generate_ai_explanation(analysis: dict, insights: list[dict] = None) -> tuple[str, bool]:
    """
    Generate an AI-powered explanation via Groq.

    Returns:
        (explanation_text: str, is_ai: bool)
        is_ai is True if AI was used, False if it fell back.
    """
    client = _get_client()
    if client is None:
        return "", False

    prompt = _build_prompt(analysis, insights)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=250,
        )
        text = response.choices[0].message.content.strip()
        logger.debug("AI explanation generated for %s", analysis.get("item_name"))
        return text, True
    except Exception as e:
        logger.warning("AI explanation failed: %s", e)
        return "", False


def generate_ai_insight_summary(insights: list[dict], sustainability: dict) -> tuple[str, bool]:
    """
    Generate an AI-powered summary of inventory insights via Groq.

    Returns:
        (summary_text: str, is_ai: bool)
    """
    client = _get_client()
    if client is None:
        return "", False

    combined = {
        "insights": [i["message"] for i in insights],
        "sustainability": sustainability.get("impact_summary", ""),
    }
    prompt = (
        "You are a direct, no-nonsense inventory operations advisor. "
        "Given the following consumption patterns and sustainability data, "
        "produce EXACTLY 3 bullet points. Each bullet MUST have these 3 lines, each on its own separate line:\n\n"
        "📌 **Pattern**: [What the data shows — name items, quantities, trends]\n\n"
        "⚠️ **Risk**: [What goes wrong if ignored — stockout date, waste amount]\n\n"
        "✅ **Action**: [Exact action to take — reorder X units of Y by Z date]\n\n\n"
        "Separate each bullet point with a blank line.\n\n"
        "Rules:\n"
        "- Use real item names and numbers from the data. No vague language.\n"
        "- Never say 'significantly higher' or 'overall high'. Use exact percentages or counts.\n"
        "- Focus on the most urgent/impactful items first.\n\n"
        f"Data:\n{json.dumps(combined, indent=2)}"
    )

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=350,
        )
        text = response.choices[0].message.content.strip()
        # Force each Pattern/Risk/Action onto its own line
        text = text.replace("⚠️", "\n⚠️").replace("✅", "\n✅")
        return text, True
    except Exception as e:
        logger.warning("AI insight summary failed: %s", e)
        return "", False


def draft_supplier_email(analysis: dict) -> str:
    """
    Use AI to draft a professional purchase order / reorder email to the supplier.
    This uses deterministic quantities (from analysis) but leverages the LLM's
    ability to write format and tone.
    """
    client = _get_client()
    if client is None:
        return "Error: Could not connect to Groq API to draft the email."

    qty = analysis.get("suggested_reorder_qty", 0)
    if qty <= 0:
        return "No reorder necessary at this time."

    prompt = (
        f"Write a professional, concise email to a supplier to order inventory.\n"
        f"Item: {analysis.get('item_name')}\n"
        f"Quantity to order: {qty} {analysis.get('unit')}\n"
        f"Current stock covers approximately {analysis.get('days_remaining', 0):.0f} days.\n"
        f"Supplier Lead Time is {analysis.get('lead_time', 0)} days, so we need "
        f"this confirmed and shipped as soon as possible.\n\n"
        f"Do not include brackets or placeholders for my name, just sign it 'Inventory Control Team'. "
        f"Keep the subject line short."
    )

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("Failed to draft email: %s", e)
        return f"Error generating email: {e}"

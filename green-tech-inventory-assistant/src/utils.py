"""
utils.py
Small shared helpers.
"""

import logging
import sys


def setup_logging(level=logging.DEBUG):
    """Configure console logging for demo/debug."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    fmt = logging.Formatter("[%(levelname)s] %(name)s — %(message)s")
    handler.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)


def fmt_days(d) -> str:
    """Human-friendly days label."""
    if d is None or d == float("inf"):
        return "∞ (no usage)"
    return f"{d:.1f} days"


def risk_emoji(risk: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk, "⚪")


def decision_emoji(decision: str) -> str:
    return {
        "reorder_now": "🔴 Reorder Now",
        "reorder_later": "🟡 Reorder Later",
        "do_not_reorder": "🟢 OK",
    }.get(decision, decision)

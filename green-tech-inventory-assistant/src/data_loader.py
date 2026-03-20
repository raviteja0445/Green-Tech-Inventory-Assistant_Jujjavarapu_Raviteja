"""
data_loader.py
Database-backed data access layer.
All reads/writes go through SQLite via SQLAlchemy.
CSV/JSON files are kept only as optional seed sources.
"""

import json
import os
import pandas as pd
from datetime import datetime, date

from src.database import (
    init_db, get_session, is_seeded,
    Item, Supplier, UsageLog, SimulatorRun,
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Test hook: set to True in tests to skip auto-seeding
_skip_auto_seed = False


def _rules_path():
    return os.path.join(DATA_DIR, "impact_rules.json")


def ensure_db():
    """Initialize DB and seed if needed (auto-run on first import)."""
    init_db()
    if not _skip_auto_seed and not is_seeded():
        from seed_db import seed
        seed()


# ──────────── Read helpers (DB → DataFrame) ────────────


def load_items() -> pd.DataFrame:
    """Load all items from the database as a DataFrame."""
    ensure_db()
    session = get_session()
    try:
        rows = session.query(Item).all()
        data = []
        for r in rows:
            data.append({
                "item_id": r.item_id,
                "item_name": r.item_name,
                "category": r.category,
                "quantity_on_hand": r.quantity_on_hand,
                "unit": r.unit,
                "expiry_date": pd.Timestamp(r.expiry_date),
                "reorder_threshold": r.reorder_threshold,
                "supplier_id": r.supplier_id,
            })
        return pd.DataFrame(data) if data else pd.DataFrame(
            columns=["item_id","item_name","category","quantity_on_hand",
                     "unit","expiry_date","reorder_threshold","supplier_id"]
        )
    finally:
        session.close()


def load_usage_logs() -> pd.DataFrame:
    """Load all usage logs from the database as a DataFrame."""
    ensure_db()
    session = get_session()
    try:
        rows = session.query(UsageLog).all()
        data = []
        for r in rows:
            data.append({
                "log_id": r.log_id,
                "item_id": r.item_id,
                "date": pd.Timestamp(r.usage_date),
                "quantity_used": r.quantity_used,
            })
        df = pd.DataFrame(data) if data else pd.DataFrame(
            columns=["log_id","item_id","date","quantity_used"]
        )
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
        return df
    finally:
        session.close()


def load_suppliers() -> pd.DataFrame:
    """Load all suppliers from the database as a DataFrame."""
    ensure_db()
    session = get_session()
    try:
        rows = session.query(Supplier).all()
        data = []
        for r in rows:
            data.append({
                "supplier_id": r.supplier_id,
                "supplier_name": r.supplier_name,
                "avg_lead_days": r.avg_lead_days,
                "local_flag": r.local_flag,
                "refurbished_flag": r.refurbished_flag,
                "packaging_score": r.packaging_score,
            })
        return pd.DataFrame(data) if data else pd.DataFrame(
            columns=["supplier_id","supplier_name","avg_lead_days",
                     "local_flag","refurbished_flag","packaging_score"]
        )
    finally:
        session.close()


def load_impact_rules() -> dict:
    """Load impact rules from JSON (config only, not runtime data)."""
    with open(_rules_path(), "r") as f:
        return json.load(f)


# ──────────── Write / CRUD helpers ────────────


def add_item(item: dict) -> str:
    """Insert a new item into the database. Returns the new item_id."""
    ensure_db()
    session = get_session()
    try:
        # Generate next item_id
        max_row = session.query(Item).order_by(Item.item_id.desc()).first()
        if max_row:
            num = int(max_row.item_id.replace("ITM", "")) + 1
        else:
            num = 1
        new_id = f"ITM{num:03d}"

        exp = item.get("expiry_date")
        if isinstance(exp, str):
            exp = datetime.strptime(exp, "%Y-%m-%d").date()
        elif isinstance(exp, datetime):
            exp = exp.date()

        new_item = Item(
            item_id=new_id,
            item_name=item["item_name"],
            category=item["category"],
            quantity_on_hand=float(item["quantity_on_hand"]),
            unit=item["unit"],
            expiry_date=exp,
            reorder_threshold=int(item.get("reorder_threshold", 10)),
            supplier_id=item["supplier_id"],
        )
        session.add(new_item)
        session.commit()
        return new_id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_item(item_id: str, updates: dict):
    """Update fields of an existing item in the database."""
    ensure_db()
    session = get_session()
    try:
        item = session.query(Item).filter_by(item_id=item_id).first()
        if not item:
            raise ValueError(f"Item {item_id} not found.")

        for k, v in updates.items():
            if k == "expiry_date":
                if isinstance(v, str):
                    v = datetime.strptime(v, "%Y-%m-%d").date()
                elif isinstance(v, datetime):
                    v = v.date()
            if hasattr(item, k):
                setattr(item, k, v)

        item.updated_at = datetime.utcnow()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def add_usage_log(item_id: str, usage_date: str, quantity_used: float):
    """Insert a usage log entry into the database."""
    ensure_db()
    session = get_session()
    try:
        if isinstance(usage_date, str):
            usage_date = datetime.strptime(usage_date, "%Y-%m-%d").date()
        elif isinstance(usage_date, datetime):
            usage_date = usage_date.date()

        log = UsageLog(
            item_id=item_id,
            usage_date=usage_date,
            quantity_used=float(quantity_used),
        )
        session.add(log)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def save_simulator_run(item_id: str, order_qty: float, lead_override: int,
                       spike_pct: float, end_stock: float,
                       stockout: bool, waste: str) -> int:
    """Persist a simulator run result to the database."""
    ensure_db()
    session = get_session()
    try:
        run = SimulatorRun(
            item_id=item_id,
            order_quantity=order_qty,
            lead_time_override=lead_override,
            demand_spike_percent=spike_pct,
            projected_end_stock=end_stock,
            stockout_risk=stockout,
            waste_risk=waste,
        )
        session.add(run)
        session.commit()
        return run.scenario_id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_item_with_supplier(item_id: str) -> dict:
    """Return merged item + supplier info as a dict from the database."""
    ensure_db()
    session = get_session()
    try:
        item = session.query(Item).filter_by(item_id=item_id).first()
        if not item:
            return {}
        sup = session.query(Supplier).filter_by(supplier_id=item.supplier_id).first()
        result = {
            "item_id": item.item_id,
            "item_name": item.item_name,
            "category": item.category,
            "quantity_on_hand": item.quantity_on_hand,
            "unit": item.unit,
            "expiry_date": pd.Timestamp(item.expiry_date),
            "reorder_threshold": item.reorder_threshold,
            "supplier_id": item.supplier_id,
        }
        if sup:
            result.update({
                "supplier_name": sup.supplier_name,
                "avg_lead_days": sup.avg_lead_days,
                "local_flag": sup.local_flag,
                "refurbished_flag": sup.refurbished_flag,
                "packaging_score": sup.packaging_score,
            })
        return result
    finally:
        session.close()


# ──────────── Full Stock Overview query ────────────


def get_full_stock_overview() -> pd.DataFrame:
    """
    Join items + suppliers for the Full Stock Overview.
    Returns all columns needed for the overview table.
    """
    ensure_db()
    session = get_session()
    try:
        rows = (
            session.query(Item, Supplier)
            .join(Supplier, Item.supplier_id == Supplier.supplier_id)
            .all()
        )
        data = []
        for item, sup in rows:
            data.append({
                "item_id": item.item_id,
                "item_name": item.item_name,
                "category": item.category,
                "quantity_on_hand": item.quantity_on_hand,
                "unit": item.unit,
                "expiry_date": item.expiry_date,
                "reorder_threshold": item.reorder_threshold,
                "supplier_id": item.supplier_id,
                "supplier_name": sup.supplier_name,
                "avg_lead_days": sup.avg_lead_days,
                "local_flag": sup.local_flag,
            })
        return pd.DataFrame(data) if data else pd.DataFrame()
    finally:
        session.close()

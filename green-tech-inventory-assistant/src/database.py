"""
database.py
SQLAlchemy ORM models and engine setup for the Green-Tech Inventory Assistant.
Uses SQLite for lightweight, zero-config local persistence.
"""

import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, Float, String, Boolean, Date, DateTime,
    ForeignKey, Text, event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "inventory.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

# Enable foreign-key enforcement for SQLite
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


# ─────────────────────── Models ───────────────────────


class Supplier(Base):
    __tablename__ = "suppliers"

    supplier_id = Column(String(10), primary_key=True)
    supplier_name = Column(String(100), nullable=False)
    avg_lead_days = Column(Integer, nullable=False, default=3)
    local_flag = Column(Boolean, default=False)
    refurbished_flag = Column(Boolean, default=False)
    packaging_score = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("Item", back_populates="supplier")


class Item(Base):
    __tablename__ = "items"

    item_id = Column(String(10), primary_key=True)
    item_name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    quantity_on_hand = Column(Float, nullable=False, default=0)
    unit = Column(String(20), nullable=False)
    expiry_date = Column(Date, nullable=False)
    reorder_threshold = Column(Integer, default=10)
    supplier_id = Column(String(10), ForeignKey("suppliers.supplier_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    supplier = relationship("Supplier", back_populates="items")
    usage_logs = relationship("UsageLog", back_populates="item", cascade="all, delete-orphan")
    simulator_runs = relationship("SimulatorRun", back_populates="item", cascade="all, delete-orphan")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(10), ForeignKey("items.item_id"), nullable=False)
    usage_date = Column(Date, nullable=False)
    quantity_used = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("Item", back_populates="usage_logs")


class SimulatorRun(Base):
    __tablename__ = "simulator_runs"

    scenario_id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(10), ForeignKey("items.item_id"), nullable=False)
    order_quantity = Column(Float, default=0)
    lead_time_override = Column(Integer)
    demand_spike_percent = Column(Float, default=0)
    projected_end_stock = Column(Float)
    stockout_risk = Column(Boolean, default=False)
    waste_risk = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)

    item = relationship("Item", back_populates="simulator_runs")


# ─────────────────────── Helpers ───────────────────────


def init_db():
    """Create all tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    Base.metadata.create_all(engine)


def get_session():
    """Return a new DB session. Caller must close it."""
    return SessionLocal()


def is_seeded() -> bool:
    """Check if the database already has seed data."""
    session = get_session()
    try:
        return session.query(Item).count() > 0
    finally:
        session.close()

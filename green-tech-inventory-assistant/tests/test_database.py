"""
test_database.py
Database integration tests — verify CRUD operations against an isolated temp SQLite.
"""

import sys
import os
import pytest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture(autouse=True)
def _use_temp_db(monkeypatch, tmp_path):
    """Redirect ALL database access to a temporary SQLite file."""
    db_path = str(tmp_path / "test_inventory.db")
    db_url = f"sqlite:///{db_path}"

    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    import src.database as dbmod
    import src.data_loader as dlmod

    test_engine = create_engine(db_url, echo=False, connect_args={"check_same_thread": False})

    @event.listens_for(test_engine, "connect")
    def _fk(dbapi_conn, _):
        c = dbapi_conn.cursor()
        c.execute("PRAGMA foreign_keys=ON")
        c.close()

    test_session_factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    # Patch the database module globals
    monkeypatch.setattr(dbmod, "engine", test_engine)
    monkeypatch.setattr(dbmod, "SessionLocal", test_session_factory)
    monkeypatch.setattr(dbmod, "DB_PATH", db_path)

    # Skip auto-seeding in tests
    monkeypatch.setattr(dlmod, "_skip_auto_seed", True)

    # Create tables
    dbmod.Base.metadata.create_all(test_engine)

    # Seed a supplier that tests will use
    session = test_session_factory()
    sup = dbmod.Supplier(
        supplier_id="SUP001", supplier_name="Test Supplier",
        avg_lead_days=3, local_flag=True, refurbished_flag=False, packaging_score=4,
    )
    session.add(sup)
    session.commit()
    session.close()

    yield


class TestDatabaseCRUD:

    def test_insert_and_fetch_item(self):
        """Create an item via data_loader and verify it appears from loaded items."""
        from src.data_loader import add_item, load_items

        new_id = add_item({
            "item_name": "Test Coffee",
            "category": "Beverages",
            "quantity_on_hand": 25,
            "unit": "kg",
            "expiry_date": "2026-06-01",
            "supplier_id": "SUP001",
            "reorder_threshold": 10,
        })

        assert new_id.startswith("ITM")

        items = load_items()
        assert len(items) == 1
        assert items.iloc[0]["item_name"] == "Test Coffee"
        assert items.iloc[0]["quantity_on_hand"] == 25

    def test_update_stock_and_verify(self):
        """Update stock and verify the new value is persisted in the database."""
        from src.data_loader import add_item, update_item, load_items

        item_id = add_item({
            "item_name": "Test Milk",
            "category": "Dairy",
            "quantity_on_hand": 50,
            "unit": "units",
            "expiry_date": "2026-04-15",
            "supplier_id": "SUP001",
            "reorder_threshold": 8,
        })

        update_item(item_id, {"quantity_on_hand": 30})

        items = load_items()
        row = items[items["item_id"] == item_id].iloc[0]
        assert row["quantity_on_hand"] == 30

    def test_add_usage_log_persists(self):
        """Insert a usage log and verify it appears in the database."""
        from src.data_loader import add_item, add_usage_log, load_usage_logs

        item_id = add_item({
            "item_name": "Test Paper",
            "category": "Office",
            "quantity_on_hand": 100,
            "unit": "reams",
            "expiry_date": "2027-01-01",
            "supplier_id": "SUP001",
            "reorder_threshold": 10,
        })

        add_usage_log(item_id, "2026-03-19", 5)
        logs = load_usage_logs()
        assert len(logs) == 1
        assert logs.iloc[0]["quantity_used"] == 5

    def test_full_stock_overview_joins(self):
        """Full Stock Overview must join items and suppliers correctly."""
        from src.data_loader import add_item, get_full_stock_overview

        add_item({
            "item_name": "Test Bananas",
            "category": "Produce",
            "quantity_on_hand": 20,
            "unit": "units",
            "expiry_date": "2026-04-01",
            "supplier_id": "SUP001",
            "reorder_threshold": 12,
        })

        overview = get_full_stock_overview()
        assert len(overview) == 1
        assert "supplier_name" in overview.columns
        assert overview.iloc[0]["supplier_name"] == "Test Supplier"

    def test_save_simulator_run(self):
        """Simulator runs are persisted correctly in the database."""
        from src.database import get_session, SimulatorRun
        from src.data_loader import add_item, save_simulator_run

        item_id = add_item({
            "item_name": "Sim Item",
            "category": "Supplies",
            "quantity_on_hand": 40,
            "unit": "packs",
            "expiry_date": "2026-12-31",
            "supplier_id": "SUP001",
            "reorder_threshold": 15,
        })

        sid = save_simulator_run(item_id, 10, 3, 0, 35.0, False, "low")
        assert sid is not None

        session = get_session()
        run = session.query(SimulatorRun).filter_by(scenario_id=sid).first()
        assert run is not None
        assert run.order_quantity == 10
        assert run.projected_end_stock == 35.0
        session.close()

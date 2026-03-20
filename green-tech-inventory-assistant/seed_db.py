"""
seed_db.py
Seeds the SQLite database with synthetic sample data.
Run once:  python seed_db.py
On subsequent runs it skips if data already exists.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import date, datetime
from src.database import init_db, get_session, is_seeded, Supplier, Item, UsageLog


def seed():
    init_db()

    if is_seeded():
        print("Database already seeded — skipping.")
        return

    session = get_session()
    try:
        # ─── Suppliers ───
        suppliers = [
            Supplier(supplier_id="SUP001", supplier_name="Bean Source Co.", avg_lead_days=3,
                     local_flag=True, refurbished_flag=False, packaging_score=4),
            Supplier(supplier_id="SUP002", supplier_name="Fresh Dairy Ltd.", avg_lead_days=1,
                     local_flag=True, refurbished_flag=False, packaging_score=3),
            Supplier(supplier_id="SUP003", supplier_name="YogurtWorld", avg_lead_days=2,
                     local_flag=False, refurbished_flag=False, packaging_score=2),
            Supplier(supplier_id="SUP004", supplier_name="CleanAll Supplies", avg_lead_days=5,
                     local_flag=False, refurbished_flag=True, packaging_score=5),
            Supplier(supplier_id="SUP005", supplier_name="Tropical Fruits Inc.", avg_lead_days=2,
                     local_flag=True, refurbished_flag=False, packaging_score=3),
            Supplier(supplier_id="SUP006", supplier_name="PaperMill Direct", avg_lead_days=4,
                     local_flag=False, refurbished_flag=True, packaging_score=4),
            Supplier(supplier_id="SUP007", supplier_name="Green Leaf Organics", avg_lead_days=2,
                     local_flag=True, refurbished_flag=False, packaging_score=5),
            Supplier(supplier_id="SUP008", supplier_name="Metro Kitchen Supply", avg_lead_days=3,
                     local_flag=False, refurbished_flag=False, packaging_score=3),
            Supplier(supplier_id="SUP009", supplier_name="EcoClean Distributors", avg_lead_days=4,
                     local_flag=True, refurbished_flag=True, packaging_score=4),
            Supplier(supplier_id="SUP010", supplier_name="BulkBrew Wholesale", avg_lead_days=5,
                     local_flag=False, refurbished_flag=False, packaging_score=2),
        ]
        session.add_all(suppliers)
        session.flush()

        # ─── Items ───
        items = [
            # --- Original 6 ---
            Item(item_id="ITM001", item_name="Coffee Beans", category="Beverages",
                 quantity_on_hand=8, unit="kg", expiry_date=date(2026, 5, 15),
                 reorder_threshold=15, supplier_id="SUP001"),
            Item(item_id="ITM002", item_name="Milk Cartons", category="Dairy",
                 quantity_on_hand=45, unit="units", expiry_date=date(2026, 3, 24),
                 reorder_threshold=10, supplier_id="SUP002"),
            Item(item_id="ITM003", item_name="Yogurt Cups", category="Dairy",
                 quantity_on_hand=6, unit="units", expiry_date=date(2026, 3, 26),
                 reorder_threshold=8, supplier_id="SUP003"),
            Item(item_id="ITM004", item_name="Cleaning Wipes", category="Supplies",
                 quantity_on_hand=120, unit="packs", expiry_date=date(2026, 12, 31),
                 reorder_threshold=20, supplier_id="SUP004"),
            Item(item_id="ITM005", item_name="Bananas", category="Produce",
                 quantity_on_hand=30, unit="units", expiry_date=date(2026, 3, 23),
                 reorder_threshold=12, supplier_id="SUP005"),
            Item(item_id="ITM006", item_name="Printer Paper", category="Office",
                 quantity_on_hand=50, unit="reams", expiry_date=date(2027, 6, 1),
                 reorder_threshold=10, supplier_id="SUP006"),
            # --- New items ---
            Item(item_id="ITM007", item_name="Green Tea Bags", category="Beverages",
                 quantity_on_hand=35, unit="packs", expiry_date=date(2026, 8, 10),
                 reorder_threshold=15, supplier_id="SUP007"),
            Item(item_id="ITM008", item_name="Butter Blocks", category="Dairy",
                 quantity_on_hand=12, unit="kg", expiry_date=date(2026, 4, 5),
                 reorder_threshold=5, supplier_id="SUP002"),
            Item(item_id="ITM009", item_name="Tomatoes", category="Produce",
                 quantity_on_hand=18, unit="kg", expiry_date=date(2026, 3, 25),
                 reorder_threshold=8, supplier_id="SUP007"),
            Item(item_id="ITM010", item_name="Paper Napkins", category="Supplies",
                 quantity_on_hand=200, unit="packs", expiry_date=date(2027, 1, 15),
                 reorder_threshold=50, supplier_id="SUP008"),
            Item(item_id="ITM011", item_name="Dish Soap", category="Supplies",
                 quantity_on_hand=15, unit="liters", expiry_date=date(2026, 11, 20),
                 reorder_threshold=8, supplier_id="SUP009"),
            Item(item_id="ITM012", item_name="Sugar Packets", category="Beverages",
                 quantity_on_hand=40, unit="packs", expiry_date=date(2026, 9, 30),
                 reorder_threshold=20, supplier_id="SUP010"),
            Item(item_id="ITM013", item_name="Avocados", category="Produce",
                 quantity_on_hand=22, unit="units", expiry_date=date(2026, 3, 24),
                 reorder_threshold=10, supplier_id="SUP005"),
            Item(item_id="ITM014", item_name="Cream Cheese", category="Dairy",
                 quantity_on_hand=9, unit="kg", expiry_date=date(2026, 4, 2),
                 reorder_threshold=4, supplier_id="SUP003"),
            Item(item_id="ITM015", item_name="Hand Sanitizer", category="Supplies",
                 quantity_on_hand=25, unit="liters", expiry_date=date(2027, 3, 1),
                 reorder_threshold=10, supplier_id="SUP009"),
            Item(item_id="ITM016", item_name="Espresso Pods", category="Beverages",
                 quantity_on_hand=5, unit="packs", expiry_date=date(2026, 7, 20),
                 reorder_threshold=12, supplier_id="SUP001"),
        ]
        session.add_all(items)
        session.flush()

        # ─── Usage Logs (7 days: Mar 13–19, 2026) ───
        usage_data = [
            # Coffee Beans — consistent ~3/day → low stock triggers reorder_now
            ("ITM001", [(13,3),(14,4),(15,2),(16,3),(17,3),(18,4),(19,3)]),
            # Milk Cartons — ~5/day, 45 units, 5d to expiry → waste risk
            ("ITM002", [(13,5),(14,6),(15,3),(16,4),(17,5),(18,6),(19,5)]),
            # Yogurt Cups — ~2/day, 6 units → reorder soon
            ("ITM003", [(13,2),(14,1),(15,3),(16,2),(17,1),(18,2),(19,2)]),
            # Cleaning Wipes — steady ~2/day, 120 on hand → do not reorder
            ("ITM004", [(13,2),(14,3),(15,1),(16,2),(17,2),(18,1),(19,2)]),
            # Bananas — high variance 5-10/day, expiring fast
            ("ITM005", [(13,6),(14,8),(15,10),(16,7),(17,5),(18,9),(19,8)]),
            # Printer Paper — low ~1/day, stable
            ("ITM006", [(13,1),(14,2),(15,0),(16,1),(17,1),(18,2),(19,1)]),
            # Green Tea Bags — moderate ~4/day
            ("ITM007", [(13,3),(14,5),(15,4),(16,3),(17,4),(18,5),(19,4)]),
            # Butter Blocks — ~1.5/day, approaching threshold
            ("ITM008", [(13,1),(14,2),(15,1),(16,2),(17,1),(18,2),(19,1)]),
            # Tomatoes — ~3/day, expiring soon
            ("ITM009", [(13,3),(14,4),(15,2),(16,3),(17,4),(18,3),(19,2)]),
            # Paper Napkins — steady ~8/day, overstocked
            ("ITM010", [(13,7),(14,9),(15,8),(16,7),(17,8),(18,9),(19,8)]),
            # Dish Soap — low ~1/day
            ("ITM011", [(13,1),(14,1),(15,0),(16,1),(17,1),(18,0),(19,1)]),
            # Sugar Packets — moderate ~3/day
            ("ITM012", [(13,3),(14,2),(15,4),(16,3),(17,2),(18,3),(19,4)]),
            # Avocados — high ~5/day, expiring fast, weekend spike
            ("ITM013", [(13,4),(14,5),(15,6),(16,4),(17,5),(18,7),(19,6)]),
            # Cream Cheese — ~1.5/day
            ("ITM014", [(13,1),(14,2),(15,1),(16,2),(17,1),(18,2),(19,1)]),
            # Hand Sanitizer — steady low ~1/day
            ("ITM015", [(13,1),(14,1),(15,1),(16,0),(17,1),(18,1),(19,1)]),
            # Espresso Pods — high ~3/day, very low stock → reorder now
            ("ITM016", [(13,2),(14,3),(15,4),(16,3),(17,2),(18,3),(19,4)]),
        ]

        for item_id, daily in usage_data:
            for day, qty in daily:
                session.add(UsageLog(
                    item_id=item_id,
                    usage_date=date(2026, 3, day),
                    quantity_used=qty,
                ))

        session.commit()
        print(f"Database seeded: {len(items)} items, {len(suppliers)} suppliers, "
              f"{sum(len(d) for _, d in usage_data)} usage logs.")
    except Exception as e:
        session.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()

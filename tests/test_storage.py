"""Testes da camada de persistência SQLite."""
import json

from src.storage import init_schema, upsert_order, get_orders_in_range


def test_init_schema_creates_all_tables(memory_db):
    init_schema(memory_db)
    cursor = memory_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row["name"] for row in cursor}
    expected = {
        "schema_version", "orders", "order_items",
        "items_cache", "categories_cache", "claims", "runs"
    }
    assert expected.issubset(tables)


def test_init_schema_is_idempotent(memory_db):
    init_schema(memory_db)
    init_schema(memory_db)  # rodar 2x não deve quebrar
    cursor = memory_db.execute("SELECT version FROM schema_version")
    versions = [row["version"] for row in cursor]
    assert versions == [1]


def test_init_schema_records_version(memory_db):
    init_schema(memory_db)
    row = memory_db.execute("SELECT version FROM schema_version").fetchone()
    assert row["version"] == 1


def test_upsert_order_inserts_new(memory_db):
    init_schema(memory_db)
    order = {
        "order_id": 1001,
        "date_closed": "2026-06-10T14:30:00.000-03:00",
        "status": "paid",
        "total_amount": 250.0,
        "marketplace_fee": 30.0,
        "shipping_cost": 15.0,
        "buyer_id": 9999,
        "raw_json": '{"id":1001}',
        "items": [
            {"item_id": "MLB1", "quantity": 1, "unit_price": 250.0}
        ],
    }
    upsert_order(memory_db, order)
    rows = memory_db.execute("SELECT * FROM orders").fetchall()
    assert len(rows) == 1
    assert rows[0]["total_amount"] == 250.0
    items = memory_db.execute("SELECT * FROM order_items").fetchall()
    assert len(items) == 1
    assert items[0]["item_id"] == "MLB1"


def test_upsert_order_updates_existing(memory_db):
    init_schema(memory_db)
    base = {
        "order_id": 1001,
        "date_closed": "2026-06-10T14:30:00.000-03:00",
        "status": "paid",
        "total_amount": 250.0,
        "marketplace_fee": 30.0,
        "shipping_cost": 15.0,
        "buyer_id": 9999,
        "raw_json": "{}",
        "items": [{"item_id": "MLB1", "quantity": 1, "unit_price": 250.0}],
    }
    upsert_order(memory_db, base)
    base["status"] = "cancelled"
    base["raw_json"] = '{"updated":true}'
    upsert_order(memory_db, base)
    rows = memory_db.execute("SELECT status FROM orders").fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "cancelled"


def test_get_orders_in_range_filters_by_date(memory_db):
    init_schema(memory_db)
    for oid, date in [(1, "2026-06-01T10:00:00"), (2, "2026-06-10T10:00:00"), (3, "2026-06-20T10:00:00")]:
        upsert_order(memory_db, {
            "order_id": oid,
            "date_closed": date,
            "status": "paid",
            "total_amount": 100.0,
            "marketplace_fee": 10.0,
            "shipping_cost": 5.0,
            "buyer_id": 1,
            "raw_json": "{}",
            "items": [],
        })
    result = get_orders_in_range(memory_db, "2026-06-05", "2026-06-15")
    assert [o["order_id"] for o in result] == [2]

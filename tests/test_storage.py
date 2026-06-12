"""Testes da camada de persistência SQLite."""
import json

from src.storage import init_schema, upsert_order, get_orders_in_range
from datetime import datetime, timedelta, timezone

from src.storage import (
    init_schema, upsert_item_cache, get_item_cache,
    upsert_category_cache, get_category_cache,
    upsert_claim, get_claims_in_range,
    log_run, get_last_run,
)


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


def test_item_cache_roundtrip(memory_db):
    init_schema(memory_db)
    upsert_item_cache(memory_db, "MLB123", "Lanterna CG 150", "MLB-cat-lights")
    cached = get_item_cache(memory_db, "MLB123", ttl_days=30)
    assert cached is not None
    assert cached["title"] == "Lanterna CG 150"


def test_item_cache_returns_none_when_stale(memory_db):
    init_schema(memory_db)
    upsert_item_cache(memory_db, "MLB123", "Lanterna", "cat")
    old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    memory_db.execute("UPDATE items_cache SET fetched_at = ? WHERE item_id = ?", (old, "MLB123"))
    memory_db.commit()
    assert get_item_cache(memory_db, "MLB123", ttl_days=30) is None


def test_category_cache_roundtrip(memory_db):
    init_schema(memory_db)
    upsert_category_cache(memory_db, "MLB-cat-1", "Iluminação")
    assert get_category_cache(memory_db, "MLB-cat-1") == "Iluminação"


def test_claims_upsert_and_range(memory_db):
    init_schema(memory_db)
    upsert_claim(memory_db, {
        "claim_id": 555, "order_id": 1001,
        "status": "opened", "date_created": "2026-06-10T12:00:00",
        "raw_json": "{}",
    })
    result = get_claims_in_range(memory_db, "2026-06-01", "2026-06-30")
    assert len(result) == 1
    assert result[0]["claim_id"] == 555


def test_log_run_and_get_last_run(memory_db):
    init_schema(memory_db)
    log_run(memory_db, week_start="2026-06-08", week_end="2026-06-14",
            pdf_path=None, status="ok", error_message=None)
    last = get_last_run(memory_db)
    assert last["status"] == "ok"
    assert last["week_start"] == "2026-06-08"

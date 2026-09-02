"""Testes da camada de persistência SQLite."""

from datetime import UTC, datetime, timedelta

from src.storage import (
    get_category_cache,
    get_item_cache,
    init_schema,
    upsert_category_cache,
    upsert_claim,
    upsert_item_cache,
    upsert_order,
)


def test_init_schema_creates_all_tables(memory_db):
    init_schema(memory_db)
    cursor = memory_db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row["name"] for row in cursor}
    expected = {
        "schema_version",
        "orders",
        "order_items",
        "items_cache",
        "categories_cache",
        "claims",
        "runs",
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
        "items": [{"item_id": "MLB1", "quantity": 1, "unit_price": 250.0}],
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


def test_upsert_order_normalizes_date_closed_to_utc(memory_db):
    """Input com fuso −03:00 é convertido para UTC (ISO com +00:00)."""
    init_schema(memory_db)
    upsert_order(
        memory_db,
        {
            "order_id": 4242,
            "date_closed": "2026-06-10T14:30:00-03:00",
            "status": "paid",
            "total_amount": 100.0,
            "marketplace_fee": 10.0,
            "shipping_cost": 5.0,
            "buyer_id": 1,
            "raw_json": "{}",
            "items": [],
        },
    )
    stored = memory_db.execute("SELECT date_closed FROM orders WHERE order_id = 4242").fetchone()[
        "date_closed"
    ]
    assert stored == "2026-06-10T17:30:00+00:00"


def test_item_cache_roundtrip(memory_db):
    init_schema(memory_db)
    upsert_item_cache(memory_db, "MLB123", "Lanterna CG 150", "MLB-cat-lights")
    cached = get_item_cache(memory_db, "MLB123", ttl_days=30)
    assert cached is not None
    assert cached["title"] == "Lanterna CG 150"


def test_item_cache_returns_none_when_stale(memory_db):
    init_schema(memory_db)
    upsert_item_cache(memory_db, "MLB123", "Lanterna", "cat")
    old = (datetime.now(UTC) - timedelta(days=60)).isoformat()
    memory_db.execute("UPDATE items_cache SET fetched_at = ? WHERE item_id = ?", (old, "MLB123"))
    memory_db.commit()
    assert get_item_cache(memory_db, "MLB123", ttl_days=30) is None


def test_category_cache_roundtrip(memory_db):
    init_schema(memory_db)
    upsert_category_cache(memory_db, "MLB-cat-1", "Iluminação")
    assert get_category_cache(memory_db, "MLB-cat-1") == "Iluminação"


def test_claims_upsert_persists_row(memory_db):
    init_schema(memory_db)
    upsert_claim(
        memory_db,
        {
            "claim_id": 555,
            "order_id": 1001,
            "status": "opened",
            "date_created": "2026-06-10T12:00:00",
            "raw_json": "{}",
        },
    )
    row = memory_db.execute("SELECT claim_id, status FROM claims WHERE claim_id = 555").fetchone()
    assert row["claim_id"] == 555
    assert row["status"] == "opened"

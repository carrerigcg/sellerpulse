"""Testes da camada de persistência SQLite."""
from src.storage import init_schema


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

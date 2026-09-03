"""Testes de src/session_store.py — stores em memória por sessão."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.auth import TokenSet
from src.session_store import InMemoryTokenStore, create_session_db


def test_inmemory_token_store_save_load_roundtrip():
    store = InMemoryTokenStore()
    tokens = TokenSet(
        access_token="APP_USR-abc",
        refresh_token="TG-xyz",
        expires_at=datetime.now(UTC) + timedelta(hours=6),
    )
    store.save(tokens)
    loaded = store.load()
    assert loaded.access_token == tokens.access_token
    assert loaded.refresh_token == tokens.refresh_token
    assert loaded.expires_at == tokens.expires_at


def test_inmemory_token_store_load_raises_when_empty():
    store = InMemoryTokenStore()
    with pytest.raises(FileNotFoundError):
        store.load()


def test_inmemory_token_store_updates_existing_seller():
    store = InMemoryTokenStore()
    old = TokenSet("APP_USR-old", "TG-old", datetime.now(UTC) + timedelta(hours=6))
    new = TokenSet("APP_USR-new", "TG-new", datetime.now(UTC) + timedelta(hours=6))
    store.save(old, seller_id=42)
    store.save(new, seller_id=42)
    loaded = store.load(seller_id=42)
    assert loaded.access_token == "APP_USR-new"


def test_inmemory_token_store_set_seller_id_migrates_anonymous_tokens():
    store = InMemoryTokenStore()
    tokens = TokenSet("APP_USR-x", "TG-y", datetime.now(UTC) + timedelta(hours=6))
    store.save(tokens)  # sem seller_id — vai pra current=0
    store.set_seller_id(12345)
    assert store.load(seller_id=12345).access_token == "APP_USR-x"
    with pytest.raises(FileNotFoundError):
        store.load(seller_id=0)


def test_create_session_db_returns_conn_with_schema():
    conn = create_session_db()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {row[0] for row in tables}
    assert "orders" in names
    assert "order_items" in names
    assert "items_cache" in names
    assert "categories_cache" in names
    assert "claims" in names
    assert "schema_version" in names
    conn.close()


def test_create_session_db_multiple_calls_return_isolated_conns():
    conn_a = create_session_db()
    conn_b = create_session_db()
    conn_a.execute(
        "INSERT INTO orders (order_id, date_closed, status, total_amount, "
        "marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at) "
        "VALUES (1, '2026-01-01', 'paid', 100.0, 0, 0, 42, '{}', '2026-01-01')"
    )
    conn_a.commit()
    count_b = conn_b.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert count_b == 0, "conn B não deve enxergar dados de conn A"
    conn_a.close()
    conn_b.close()

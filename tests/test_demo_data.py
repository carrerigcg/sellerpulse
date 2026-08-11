"""Testes do gerador de dados sintéticos determinístico."""

from __future__ import annotations

import hashlib
import sqlite3

from src.demo_data import (
    ANCHOR_TIMESTAMP,
    DEFAULT_SEED,
    generate_catalog,
    generate_claims,
    generate_demo_db,
    generate_orders,
    write_row,
)


def test_write_row_uses_anchor_timestamp_for_fetched_at(memory_db: sqlite3.Connection) -> None:
    memory_db.executescript(
        "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, fetched_at TEXT NOT NULL)"
    )
    write_row(memory_db, "t", {"id": 1, "name": "A"})
    row = memory_db.execute("SELECT fetched_at FROM t WHERE id = 1").fetchone()
    assert row["fetched_at"] == ANCHOR_TIMESTAMP


def test_write_row_is_deterministic_across_calls(tmp_path) -> None:
    def build_and_hash() -> str:
        db_path = tmp_path / "d.db"
        if db_path.exists():
            db_path.unlink()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript(
            "CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT, fetched_at TEXT NOT NULL)"
        )
        for i in range(10):
            write_row(conn, "t", {"id": i, "name": f"row-{i}"})
        conn.commit()
        conn.close()
        return hashlib.sha256(db_path.read_bytes()).hexdigest()

    # Prova determinismo same-process. Cross-run precisa de VACUUM
    # (adicionado no generate_demo_db da Task 6).
    assert build_and_hash() == build_and_hash()


def test_generate_catalog_is_deterministic() -> None:
    a = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    b = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    assert a == b


def test_generate_catalog_shapes() -> None:
    result = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    assert len(result["categories"]) == 10
    assert len(result["products"]) == 50
    assert all("category_id" in c for c in result["categories"])
    assert all("name" in c for c in result["categories"])
    assert all("item_id" in p for p in result["products"])
    assert all("title" in p for p in result["products"])
    assert all("category_id" in p for p in result["products"])
    assert all("unit_price" in p for p in result["products"])
    assert all(50.0 <= p["unit_price"] <= 800.0 for p in result["products"])
    assert all(
        p["category_id"] in {c["category_id"] for c in result["categories"]}
        for p in result["products"]
    )


def test_generate_catalog_different_seeds_produce_different_output() -> None:
    a = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    b = generate_catalog(seed=DEFAULT_SEED + 1, n_categories=10, n_products=50)
    # Categorias são hardcoded → iguais entre seeds. Produtos usam Faker + rng
    # semeados → devem diferir.
    assert a["categories"] == b["categories"]
    assert a["products"] != b["products"]


def test_generate_orders_is_deterministic() -> None:
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    a = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=12)
    b = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=12)
    assert a == b


def test_generate_orders_volume_in_expected_range() -> None:
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    orders = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=12)
    # 12 semanas × ~30 orders = ~360, com variação Poisson
    assert 300 <= len(orders) <= 420


def test_generate_orders_have_required_fields() -> None:
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    orders = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=12)
    required = {
        "order_id",
        "date_closed",
        "status",
        "total_amount",
        "marketplace_fee",
        "shipping_cost",
        "buyer_id",
        "raw_json",
        "items",
    }
    assert required.issubset(orders[0].keys())
    assert orders[0]["items"], "each order must have at least one item"
    assert {"item_id", "quantity", "unit_price"}.issubset(orders[0]["items"][0].keys())


def test_generate_orders_cancellation_rate_approx_5pct() -> None:
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    orders = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=12)
    cancelled = sum(1 for o in orders if o["status"] == "cancelled")
    ratio = cancelled / len(orders)
    assert 0.02 <= ratio <= 0.10  # ~5% ± tolerância pra amostra pequena


def test_generate_claims_is_deterministic() -> None:
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    orders = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=12)
    a = generate_claims(orders=orders, seed=DEFAULT_SEED, rate=0.04)
    b = generate_claims(orders=orders, seed=DEFAULT_SEED, rate=0.04)
    assert a == b


def test_generate_claims_only_references_paid_orders() -> None:
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    orders = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=12)
    paid_ids = {o["order_id"] for o in orders if o["status"] == "paid"}
    claims = generate_claims(orders=orders, seed=DEFAULT_SEED, rate=0.04)
    assert claims, "expected at least one claim"
    for c in claims:
        assert c["order_id"] in paid_ids


def test_generate_claims_have_required_fields() -> None:
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    orders = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=12)
    claims = generate_claims(orders=orders, seed=DEFAULT_SEED, rate=0.04)
    required = {"claim_id", "order_id", "status", "date_created", "raw_json"}
    assert required.issubset(claims[0].keys())


def test_generate_demo_db_produces_byte_identical_file(tmp_path) -> None:
    def build_and_hash() -> str:
        db_path = tmp_path / "demo.db"
        if db_path.exists():
            db_path.unlink()
        generate_demo_db(db_path)
        return hashlib.sha256(db_path.read_bytes()).hexdigest()

    assert build_and_hash() == build_and_hash()


def test_generate_demo_db_populates_all_tables(tmp_path) -> None:
    db_path = tmp_path / "demo.db"
    generate_demo_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    orders_count = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()["c"]
    items_count = conn.execute("SELECT COUNT(*) AS c FROM order_items").fetchone()["c"]
    items_cache_count = conn.execute("SELECT COUNT(*) AS c FROM items_cache").fetchone()["c"]
    categories_count = conn.execute("SELECT COUNT(*) AS c FROM categories_cache").fetchone()["c"]
    claims_count = conn.execute("SELECT COUNT(*) AS c FROM claims").fetchone()["c"]

    assert 300 <= orders_count <= 420
    assert items_count >= orders_count  # >=1 item por pedido
    assert items_cache_count == 50
    assert categories_count == 10
    assert claims_count >= 1
    conn.close()

"""Testes do gerador de dados sintéticos determinístico."""

from __future__ import annotations

import hashlib
import sqlite3

from src.demo_data import ANCHOR_TIMESTAMP, DEFAULT_SEED, generate_catalog, write_row


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

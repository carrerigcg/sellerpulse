"""Testes da camada de segmentação."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest


def _seed_minimal_schema(conn: sqlite3.Connection) -> None:
    """Cria as tabelas mínimas necessárias para segmentation (subset de storage.py)."""
    conn.executescript(
        """
        CREATE TABLE orders (
            order_id INTEGER PRIMARY KEY,
            date_closed TEXT NOT NULL,
            status TEXT NOT NULL,
            total_amount REAL NOT NULL,
            marketplace_fee REAL NOT NULL DEFAULT 0,
            shipping_cost REAL NOT NULL DEFAULT 0,
            buyer_id INTEGER,
            raw_json TEXT DEFAULT '{}',
            fetched_at TEXT DEFAULT ''
        );
        CREATE TABLE order_items (
            order_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            PRIMARY KEY (order_id, item_id)
        );
        CREATE TABLE items_cache (
            item_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category_id TEXT NOT NULL,
            fetched_at TEXT DEFAULT ''
        );
        CREATE TABLE categories_cache (
            category_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            fetched_at TEXT DEFAULT ''
        );
        """
    )


@pytest.fixture
def abc_conn() -> sqlite3.Connection:
    """Cenário controlado para ABC: 4 produtos com receitas conhecidas.

    Produto A: 800 (40% do total)
    Produto B: 800 (40% — juntos com A somam 80% → ambos classe A)
    Produto C: 300 (15% — classe B, cai na fronteira 95%)
    Produto D: 100 (5% — classe C)
    Total: 2000
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _seed_minimal_schema(conn)
    conn.execute(
        "INSERT INTO categories_cache (category_id, name) VALUES ('CAT1', 'Cat Um')"
    )
    for item_id, title in [
        ("A", "Prod A"),
        ("B", "Prod B"),
        ("C", "Prod C"),
        ("D", "Prod D"),
    ]:
        conn.execute(
            "INSERT INTO items_cache (item_id, title, category_id) VALUES (?, ?, 'CAT1')",
            (item_id, title),
        )
    # Cada order tem 1 item com quantity=1 e unit_price = receita alvo.
    orders = [
        (1, "2026-07-01T10:00:00", "paid", 800, "A", 800),
        (2, "2026-07-02T10:00:00", "paid", 800, "B", 800),
        (3, "2026-07-03T10:00:00", "paid", 300, "C", 300),
        (4, "2026-07-04T10:00:00", "paid", 100, "D", 100),
    ]
    for order_id, date_closed, status, total, item_id, unit_price in orders:
        conn.execute(
            "INSERT INTO orders (order_id, date_closed, status, total_amount, buyer_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (order_id, date_closed, status, total, 1000 + order_id),
        )
        conn.execute(
            "INSERT INTO order_items (order_id, item_id, quantity, unit_price) VALUES (?, ?, 1, ?)",
            (order_id, item_id, unit_price),
        )
    conn.commit()
    yield conn
    conn.close()


from src.segmentation import abc_pareto  # noqa: E402 — after fixtures for readability


def test_abc_pareto_returns_dataframe_with_expected_columns(abc_conn: sqlite3.Connection) -> None:
    df = abc_pareto(abc_conn, "2026-07-01", "2026-08-01")
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == {
        "sku",
        "titulo",
        "receita",
        "receita_pct",
        "receita_acumulada_pct",
        "classe",
    }
    # Ordenado desc por receita.
    assert df["receita"].is_monotonic_decreasing


def test_abc_pareto_pct_sums_to_100(abc_conn: sqlite3.Connection) -> None:
    df = abc_pareto(abc_conn, "2026-07-01", "2026-08-01")
    assert df["receita_pct"].sum() == pytest.approx(100.0, abs=0.01)


def test_abc_pareto_acumulada_is_monotonic(abc_conn: sqlite3.Connection) -> None:
    df = abc_pareto(abc_conn, "2026-07-01", "2026-08-01")
    assert df["receita_acumulada_pct"].is_monotonic_increasing


def test_abc_pareto_classifica_por_regra_80_15_5(abc_conn: sqlite3.Connection) -> None:
    """Fixture tem 2 produtos somando 80% (classe A), 1 até 95% (B), 1 sobrando (C)."""
    df = abc_pareto(abc_conn, "2026-07-01", "2026-08-01")
    classes_por_sku = dict(zip(df["sku"], df["classe"], strict=True))
    assert classes_por_sku == {"A": "A", "B": "A", "C": "B", "D": "C"}


def test_abc_pareto_empty_window_returns_empty_df(abc_conn: sqlite3.Connection) -> None:
    df = abc_pareto(abc_conn, "2020-01-01", "2020-01-02")
    assert df.empty
    assert set(df.columns) == {
        "sku",
        "titulo",
        "receita",
        "receita_pct",
        "receita_acumulada_pct",
        "classe",
    }

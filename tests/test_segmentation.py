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


@pytest.fixture
def rfm_conn() -> sqlite3.Connection:
    """Cenário controlado para RFM: 5 buyers com perfis distintos.

    Base: janela date_from='2026-05-01' até date_to='2026-08-01' (92 dias).
    date_to funciona como "hoje" para cálculo de recency.

    Buyer 1 (Champion): 5 compras, alta receita, última em jul → R~5 F~5 M~5
    Buyer 2 (Loyal):    4 compras, média receita, última em jul → F alto
    Buyer 3 (At Risk):  3 compras alto valor, última em maio  → R baixo, F/M médios
    Buyer 4 (New):      1 compra em jul                        → R alto, F baixo
    Buyer 5 (Hibernating): 1 compra pequena em maio           → tudo baixo
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _seed_minimal_schema(conn)
    # Um único item para simplificar (não usa items_cache aqui, mas mantém consistência).
    conn.execute(
        "INSERT INTO categories_cache (category_id, name) VALUES ('C', 'Cat')"
    )
    conn.execute(
        "INSERT INTO items_cache (item_id, title, category_id) VALUES ('X', 'X', 'C')"
    )
    orders_by_buyer: list[tuple[int, str, float]] = [
        # (buyer_id, date_closed, total_amount)
        # Buyer 1 — Champion (5 compras, gasto alto, recente)
        (1, "2026-05-10T10:00:00", 500),
        (1, "2026-06-01T10:00:00", 600),
        (1, "2026-06-15T10:00:00", 700),
        (1, "2026-07-01T10:00:00", 500),
        (1, "2026-07-20T10:00:00", 800),
        # Buyer 2 — Loyal (4 compras, gasto médio, recente)
        (2, "2026-05-15T10:00:00", 200),
        (2, "2026-06-05T10:00:00", 300),
        (2, "2026-06-20T10:00:00", 200),
        (2, "2026-07-10T10:00:00", 400),
        # Buyer 3 — At Risk (3 compras altas, mas parou em maio)
        (3, "2026-05-05T10:00:00", 500),
        (3, "2026-05-15T10:00:00", 600),
        (3, "2026-05-25T10:00:00", 700),
        # Buyer 4 — New (1 compra recente)
        (4, "2026-07-25T10:00:00", 150),
        # Buyer 5 — Hibernating (1 compra pequena, faz tempo)
        (5, "2026-05-02T10:00:00", 50),
    ]
    for oid, (buyer, date_closed, total) in enumerate(orders_by_buyer, start=1):
        conn.execute(
            "INSERT INTO orders (order_id, date_closed, status, total_amount, buyer_id) "
            "VALUES (?, ?, 'paid', ?, ?)",
            (oid, date_closed, total, buyer),
        )
        conn.execute(
            "INSERT INTO order_items (order_id, item_id, quantity, unit_price) VALUES (?, 'X', 1, ?)",
            (oid, total),
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


from src.segmentation import rfm_scores  # noqa: E402


def test_rfm_returns_expected_columns(rfm_conn: sqlite3.Connection) -> None:
    df = rfm_scores(rfm_conn, "2026-05-01", "2026-08-01")
    assert set(df.columns) == {
        "buyer_id",
        "recency_dias",
        "frequency",
        "monetary",
        "r_score",
        "f_score",
        "m_score",
        "segmento",
    }


def test_rfm_one_row_per_buyer(rfm_conn: sqlite3.Connection) -> None:
    df = rfm_scores(rfm_conn, "2026-05-01", "2026-08-01")
    # Fixture tem 5 buyers distintos.
    assert len(df) == 5
    assert df["buyer_id"].nunique() == 5


def test_rfm_scores_are_in_range_1_to_5(rfm_conn: sqlite3.Connection) -> None:
    df = rfm_scores(rfm_conn, "2026-05-01", "2026-08-01")
    assert df["r_score"].between(1, 5).all()
    assert df["f_score"].between(1, 5).all()
    assert df["m_score"].between(1, 5).all()


def test_rfm_segment_partition_sums_to_total_buyers(rfm_conn: sqlite3.Connection) -> None:
    df = rfm_scores(rfm_conn, "2026-05-01", "2026-08-01")
    # Cada buyer tem exatamente 1 segmento — soma da contagem = total.
    assert df["segmento"].value_counts().sum() == len(df)


def test_rfm_buyer1_is_champion(rfm_conn: sqlite3.Connection) -> None:
    """Buyer com R/F/M mais altos deve virar Champions."""
    df = rfm_scores(rfm_conn, "2026-05-01", "2026-08-01")
    buyer1_seg = df.loc[df["buyer_id"] == 1, "segmento"].iloc[0]
    assert buyer1_seg == "Champions"


def test_rfm_buyer5_is_hibernating(rfm_conn: sqlite3.Connection) -> None:
    """Buyer com R/F/M mais baixos deve virar Hibernating."""
    df = rfm_scores(rfm_conn, "2026-05-01", "2026-08-01")
    buyer5_seg = df.loc[df["buyer_id"] == 5, "segmento"].iloc[0]
    assert buyer5_seg == "Hibernating"


def test_rfm_buyer3_is_at_risk(rfm_conn: sqlite3.Connection) -> None:
    """Buyer com F/M médios mas recency baixa (parou em maio) → At Risk."""
    df = rfm_scores(rfm_conn, "2026-05-01", "2026-08-01")
    buyer3_seg = df.loc[df["buyer_id"] == 3, "segmento"].iloc[0]
    assert buyer3_seg == "At Risk"


def test_rfm_buyer4_is_new(rfm_conn: sqlite3.Connection) -> None:
    """Buyer com 1 compra recente → New."""
    df = rfm_scores(rfm_conn, "2026-05-01", "2026-08-01")
    buyer4_seg = df.loc[df["buyer_id"] == 4, "segmento"].iloc[0]
    assert buyer4_seg == "New"


def test_rfm_empty_window_returns_empty_df(rfm_conn: sqlite3.Connection) -> None:
    df = rfm_scores(rfm_conn, "2020-01-01", "2020-01-02")
    assert df.empty
    assert set(df.columns) == {
        "buyer_id",
        "recency_dias",
        "frequency",
        "monetary",
        "r_score",
        "f_score",
        "m_score",
        "segmento",
    }

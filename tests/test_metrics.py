"""Testes da camada de métricas financeiras e operacionais."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from src.metrics import COST_ESTIMATE_RATE, fluxo_financeiro, top_produtos


@pytest.fixture(scope="module")
def demo_conn() -> sqlite3.Connection:
    """Abre `data/demo.db` (versionado, determinístico) read-only."""
    db_path = Path("data/demo.db")
    assert db_path.exists(), "Rode `python -m src.main regerar-dados` antes."
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_fluxo_financeiro_returns_dataframe_with_expected_columns(
    demo_conn: sqlite3.Connection,
) -> None:
    df = fluxo_financeiro(demo_conn, "2026-07-25", "2026-08-01")
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == {
        "date",
        "receita_bruta",
        "taxas_ml",
        "frete",
        "custo_estimado",
        "liquido",
    }


def test_fluxo_financeiro_custo_estimado_applies_rate(
    demo_conn: sqlite3.Connection,
) -> None:
    """Custo estimado é receita_bruta × COST_ESTIMATE_RATE (arredondado 2)."""
    df = fluxo_financeiro(demo_conn, "2026-05-01", "2026-08-01")
    expected = (df["receita_bruta"] * COST_ESTIMATE_RATE).round(2)
    pd.testing.assert_series_equal(df["custo_estimado"], expected, check_names=False)


def test_fluxo_financeiro_only_paid_orders(demo_conn: sqlite3.Connection) -> None:
    """Cancelados não entram na receita — soma tem que bater com paid-only."""
    df = fluxo_financeiro(demo_conn, "2026-05-01", "2026-08-01")
    manual = demo_conn.execute(
        "SELECT SUM(total_amount) FROM orders "
        "WHERE status='paid' AND date_closed>='2026-05-01' AND date_closed<'2026-08-01'"
    ).fetchone()[0]
    assert df["receita_bruta"].sum() == pytest.approx(manual)


def test_fluxo_financeiro_liquido_is_lower_than_receita(
    demo_conn: sqlite3.Connection,
) -> None:
    df = fluxo_financeiro(demo_conn, "2026-05-01", "2026-08-01")
    assert (df["liquido"] < df["receita_bruta"]).all()


def test_fluxo_financeiro_empty_window_returns_empty_df(
    demo_conn: sqlite3.Connection,
) -> None:
    df = fluxo_financeiro(demo_conn, "2020-01-01", "2020-01-02")
    assert df.empty
    assert set(df.columns) == {
        "date",
        "receita_bruta",
        "taxas_ml",
        "frete",
        "custo_estimado",
        "liquido",
    }


def test_top_produtos_returns_dict_with_two_dataframes(
    demo_conn: sqlite3.Connection,
) -> None:
    result = top_produtos(demo_conn, "2026-05-01", "2026-08-01", n=5)
    assert set(result.keys()) == {"produtos", "categorias"}
    assert isinstance(result["produtos"], pd.DataFrame)
    assert isinstance(result["categorias"], pd.DataFrame)


def test_top_produtos_respects_n_limit(demo_conn: sqlite3.Connection) -> None:
    result = top_produtos(demo_conn, "2026-05-01", "2026-08-01", n=3)
    assert len(result["produtos"]) == 3
    assert len(result["categorias"]) == 3


def test_top_produtos_ordered_by_revenue_desc(demo_conn: sqlite3.Connection) -> None:
    result = top_produtos(demo_conn, "2026-05-01", "2026-08-01", n=10)
    prods = result["produtos"]
    assert prods["receita"].is_monotonic_decreasing
    cats = result["categorias"]
    assert cats["receita"].is_monotonic_decreasing


def test_top_produtos_columns(demo_conn: sqlite3.Connection) -> None:
    result = top_produtos(demo_conn, "2026-05-01", "2026-08-01", n=5)
    assert set(result["produtos"].columns) == {
        "item_id",
        "title",
        "category_name",
        "unidades",
        "receita",
    }
    assert set(result["categorias"].columns) == {
        "category_id",
        "category_name",
        "unidades",
        "receita",
    }


def test_top_produtos_empty_window_returns_empty_dfs(
    demo_conn: sqlite3.Connection,
) -> None:
    """Janela vazia — dfs vazios preservando colunas (paridade com fluxo_financeiro)."""
    result = top_produtos(demo_conn, "2020-01-01", "2020-01-02", n=5)
    assert result["produtos"].empty
    assert result["categorias"].empty
    assert set(result["produtos"].columns) == {
        "item_id",
        "title",
        "category_name",
        "unidades",
        "receita",
    }
    assert set(result["categorias"].columns) == {
        "category_id",
        "category_name",
        "unidades",
        "receita",
    }

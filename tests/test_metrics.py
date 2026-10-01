"""Testes da camada de métricas financeiras e operacionais."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from src.metrics import (
    COST_ESTIMATE_RATE,
    SEM_CATEGORIA,
    fluxo_financeiro,
    reputacao_devolucao,
    top_produtos,
)
from src.storage import connect, upsert_category_cache, upsert_item_cache, upsert_order


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


# ---------- anúncios apagados / categorias fora do cache ----------
#
# `data/demo.db` tem 0 itens vendidos sem linha em items_cache e 0 categorias
# fora de categories_cache, então ele não exercita este caminho. Estes testes
# montam o cenário explicitamente.


def _receita_crua(conn: sqlite3.Connection, date_from: str, date_to: str) -> float:
    """SUM(quantity * unit_price) direto de order_items — sem passar por cache.

    É a referência contra a qual os rankings têm que fechar: foi assim que o
    bug do INNER JOIN foi encontrado no `backend/`. Checar só "a linha aparece"
    passaria mesmo com a receita errada.
    """
    return conn.execute(
        "SELECT ROUND(SUM(oi.quantity*oi.unit_price),2) FROM order_items oi "
        "JOIN orders o ON o.order_id = oi.order_id "
        "WHERE o.status='paid' AND o.date_closed>=? AND o.date_closed<?",
        (date_from, date_to),
    ).fetchone()[0]


@pytest.fixture
def conn_com_anuncio_apagado() -> sqlite3.Connection:
    """Banco com os três casos que os INNER JOINs engoliam.

    - MLB1 / MLB2: em items_cache, categoria CAT1 em categories_cache (normal).
    - MLB3: em items_cache, mas a categoria dele NÃO entrou em
      categories_cache — título conhecido, categoria desconhecida.
    - MLB404 / MLB405: anúncios apagados no ML, nada em items_cache.

    Receita total paga: R$ 1.101,00 (CAT1 = 520,00; desconhecidos = 581,00).
    """
    conn = connect(":memory:")
    upsert_category_cache(conn, "CAT1", "Áudio")
    for item_id, titulo, cat_id in [
        ("MLB1", "Fone Bluetooth", "CAT1"),
        ("MLB2", "Caixa de Som", "CAT1"),
        ("MLB3", "Cabo USB-C", "CAT_FORA_DO_CACHE"),
    ]:
        upsert_item_cache(conn, item_id, titulo, cat_id)

    pedidos = [
        (1, "2026-07-05T10:00:00+00:00", [("MLB1", 2, 150.00)]),  # 300,00 CAT1
        (2, "2026-07-06T10:00:00+00:00", [("MLB2", 1, 220.00)]),  # 220,00 CAT1
        (3, "2026-07-07T10:00:00+00:00", [("MLB3", 3, 30.00)]),  # 90,00 sem cat
        (4, "2026-07-08T10:00:00+00:00", [("MLB404", 5, 80.00)]),  # 400,00 apagado
        (5, "2026-07-09T10:00:00+00:00", [("MLB405", 2, 45.50)]),  # 91,00 apagado
    ]
    for order_id, date_closed, itens in pedidos:
        upsert_order(
            conn,
            {
                "order_id": order_id,
                "date_closed": date_closed,
                "status": "paid",
                "total_amount": sum(q * p for _, q, p in itens),
                "marketplace_fee": 0.0,
                "shipping_cost": 0.0,
                "buyer_id": 1001,
                "raw_json": "{}",
                "items": [{"item_id": i, "quantity": q, "unit_price": p} for i, q, p in itens],
            },
        )
    conn.commit()
    yield conn
    conn.close()


def test_top_produtos_mantem_item_sem_items_cache(
    conn_com_anuncio_apagado: sqlite3.Connection,
) -> None:
    """Anúncio apagado no ML não tem linha em items_cache — mas a venda foi real.

    O INNER JOIN fazia o item sumir do ranking junto com a receita (11,2% numa
    loja real), e a tela Produtos divergia da Executive. O título cai pro
    próprio SKU.
    """
    res = top_produtos(conn_com_anuncio_apagado, "2026-07-01", "2026-08-01", n=100)
    prod = res["produtos"]

    assert set(prod["item_id"]) == {"MLB1", "MLB2", "MLB3", "MLB404", "MLB405"}
    esperado = _receita_crua(conn_com_anuncio_apagado, "2026-07-01", "2026-08-01")
    assert esperado == pytest.approx(1101.0)
    assert prod["receita"].sum() == pytest.approx(esperado), "receita diverge da soma crua"
    assert prod["unidades"].sum() == 13

    por_item = prod.set_index("item_id")
    # Fallback do título = o próprio SKU; quem está em cache mantém o título real.
    assert por_item.loc["MLB404", "title"] == "MLB404"
    assert por_item.loc["MLB405", "title"] == "MLB405"
    assert por_item.loc["MLB1", "title"] == "Fone Bluetooth"
    # MLB3 está em cache: o título é conhecido, só a categoria é que não é.
    assert por_item.loc["MLB3", "title"] == "Cabo USB-C"
    assert prod["title"].notna().all()
    # O anúncio apagado é o maior do período, então lidera o ranking.
    assert prod.iloc[0]["item_id"] == "MLB404"
    assert prod.iloc[0]["receita"] == pytest.approx(400.0)


def test_top_produtos_categoria_desconhecida_nao_vira_categoria_real(
    conn_com_anuncio_apagado: sqlite3.Connection,
) -> None:
    """Categoria desconhecida é rótulo explícito, nunca uma categoria herdada."""
    res = top_produtos(conn_com_anuncio_apagado, "2026-07-01", "2026-08-01", n=100)
    por_item = res["produtos"].set_index("item_id")

    assert por_item.loc["MLB404", "category_name"] == SEM_CATEGORIA
    assert por_item.loc["MLB405", "category_name"] == SEM_CATEGORIA
    assert por_item.loc["MLB3", "category_name"] == SEM_CATEGORIA
    assert por_item.loc["MLB1", "category_name"] == "Áudio"
    assert por_item.loc["MLB2", "category_name"] == "Áudio"


def test_top_categorias_isola_desconhecidos_num_balde_com_category_id_nulo(
    conn_com_anuncio_apagado: sqlite3.Connection,
) -> None:
    """Descartar o desconhecido quebra o total; jogá-lo numa categoria real
    atribui venda a quem não vendeu. A saída certa é um balde próprio, sem
    category_id, com o total fechando."""
    res = top_produtos(conn_com_anuncio_apagado, "2026-07-01", "2026-08-01", n=100)
    cat = res["categorias"]

    # As categorias reais ficam intactas — não absorvem receita de desconhecido.
    reais = cat[cat["category_id"].notna()].set_index("category_id")
    assert reais.loc["CAT1", "receita"] == pytest.approx(520.0)
    assert reais.loc["CAT1", "unidades"] == 3

    # E os desconhecidos viram exatamente UM balde, sem category_id.
    sem = cat[cat["category_id"].isna()]
    assert len(sem) == 1, "desconhecidos deviam formar um balde único"
    assert sem.iloc[0]["category_name"] == SEM_CATEGORIA
    assert sem.iloc[0]["receita"] == pytest.approx(581.0)  # 400 + 91 + 90
    assert sem.iloc[0]["unidades"] == 10
    assert cat.iloc[0]["category_name"] == SEM_CATEGORIA  # 581 é o maior


def test_top_categorias_reconcilia_com_a_receita_paga_total(
    conn_com_anuncio_apagado: sqlite3.Connection,
) -> None:
    """A soma do ranking de categorias tem que fechar com a receita crua.

    É o invariante que o INNER JOIN violava silenciosamente: sem erro nenhum,
    a tela Produtos somava menos que a Executive.
    """
    res = top_produtos(conn_com_anuncio_apagado, "2026-07-01", "2026-08-01", n=100)
    esperado = _receita_crua(conn_com_anuncio_apagado, "2026-07-01", "2026-08-01")

    assert res["categorias"]["receita"].sum() == pytest.approx(esperado)
    assert res["categorias"]["unidades"].sum() == 13
    # Produtos e categorias têm que concordar entre si também.
    assert res["produtos"]["receita"].sum() == pytest.approx(res["categorias"]["receita"].sum())


def test_reputacao_devolucao_returns_expected_keys(
    demo_conn: sqlite3.Connection,
) -> None:
    result = reputacao_devolucao(demo_conn, "2026-05-01", "2026-08-01")
    assert set(result.keys()) == {
        "nivel_ml",
        "taxa_devolucao_pct",
        "claims_ativos",
        "claims_total",
        "alertas",
    }


def test_reputacao_devolucao_types(demo_conn: sqlite3.Connection) -> None:
    result = reputacao_devolucao(demo_conn, "2026-05-01", "2026-08-01")
    assert result["nivel_ml"] in {"Verde", "Amarelo", "Vermelho"}
    assert isinstance(result["taxa_devolucao_pct"], float)
    assert isinstance(result["claims_ativos"], int)
    assert isinstance(result["claims_total"], int)
    assert isinstance(result["alertas"], list)
    assert all(isinstance(a, str) for a in result["alertas"])


def test_reputacao_devolucao_taxa_matches_manual_calc(
    demo_conn: sqlite3.Connection,
) -> None:
    result = reputacao_devolucao(demo_conn, "2026-05-01", "2026-08-01")
    paid = demo_conn.execute(
        "SELECT COUNT(*) FROM orders "
        "WHERE status='paid' AND date_closed>='2026-05-01' AND date_closed<'2026-08-01'"
    ).fetchone()[0]
    claims = demo_conn.execute(
        "SELECT COUNT(*) FROM claims WHERE date_created>='2026-05-01' AND date_created<'2026-08-01'"
    ).fetchone()[0]
    expected = round(100.0 * claims / paid, 2) if paid else 0.0
    assert result["taxa_devolucao_pct"] == pytest.approx(expected)
    assert result["claims_total"] == claims


def test_reputacao_devolucao_empty_window_returns_verde_zero(
    demo_conn: sqlite3.Connection,
) -> None:
    result = reputacao_devolucao(demo_conn, "2020-01-01", "2020-01-02")
    assert result["nivel_ml"] == "Verde"
    assert result["taxa_devolucao_pct"] == 0.0
    assert result["claims_total"] == 0
    assert result["claims_ativos"] == 0
    assert result["alertas"] == []

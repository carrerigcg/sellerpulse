"""Testes da camada de segmentação."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.segmentation import _assign_segment, abc_pareto, cohort_produto, rfm_scores


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
    conn.execute("INSERT INTO categories_cache (category_id, name) VALUES ('CAT1', 'Cat Um')")
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
    """Cenário controlado para RFM: 6 buyers com perfis distintos.

    Base: janela date_from='2026-05-01' até date_to='2026-08-01' (92 dias).
    date_to funciona como "hoje" para cálculo de recency.

    Buyer 1 (Champion): 5 compras, alta receita, última em jul → R~5 F~5 M~5
    Buyer 2 (Loyal):    4 compras, média receita, última em jul → F alto
    Buyer 3 (At Risk):  3 compras alto valor, última em maio  → R baixo, F/M médios
    Buyer 4 (New):      1 compra em jul                        → R alto, F baixo
    Buyer 5 (Hibernating): 1 compra pequena em maio           → tudo baixo
    Buyer 6 (Others):   2 compras mid-tier em jun              → R/F/M médios, sem regra nomeada
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _seed_minimal_schema(conn)
    # Um único item para simplificar (não usa items_cache aqui, mas mantém consistência).
    conn.execute("INSERT INTO categories_cache (category_id, name) VALUES ('C', 'Cat')")
    conn.execute("INSERT INTO items_cache (item_id, title, category_id) VALUES ('X', 'X', 'C')")
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
        # Buyer 6 — Others (mid-tier em tudo: sem regra nomeada casa)
        (6, "2026-06-15T10:00:00", 250),
        (6, "2026-06-25T10:00:00", 250),
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


@pytest.fixture
def abc_conn_com_anuncio_apagado() -> sqlite3.Connection:
    """2 produtos em items_cache + 1 anúncio apagado (sem linha no cache).

    `data/demo.db` tem 0 itens vendidos sem linha em items_cache, então o
    banco demo não exercita este caminho — daí a fixture dedicada.

    Receita: MLB1 = 600, MLB404 = 300, MLB2 = 100. Total 1000.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _seed_minimal_schema(conn)
    conn.execute("INSERT INTO categories_cache (category_id, name) VALUES ('CAT1', 'Cat Um')")
    for item_id, title in [("MLB1", "Produto 1"), ("MLB2", "Produto 2")]:
        conn.execute(
            "INSERT INTO items_cache (item_id, title, category_id) VALUES (?, ?, 'CAT1')",
            (item_id, title),
        )
    # MLB404 nao tem items_cache: anuncio apagado no ML.
    for order_id, item_id, receita in [
        (1, "MLB1", 600.0),
        (2, "MLB404", 300.0),
        (3, "MLB2", 100.0),
    ]:
        conn.execute(
            "INSERT INTO orders (order_id, date_closed, status, total_amount, buyer_id) "
            "VALUES (?, '2026-07-10T10:00:00', 'paid', ?, 1001)",
            (order_id, receita),
        )
        conn.execute(
            "INSERT INTO order_items (order_id, item_id, quantity, unit_price) VALUES (?, ?, 1, ?)",
            (order_id, item_id, receita),
        )
    conn.commit()
    yield conn
    conn.close()


def test_abc_pareto_mantem_item_sem_items_cache(
    abc_conn_com_anuncio_apagado: sqlite3.Connection,
) -> None:
    """Anúncio apagado no ML não tem linha em items_cache — a venda foi real.

    Aqui o INNER JOIN era pior do que num ranking simples: além de perder a
    linha, o total encolhia e as classes A/B/C de TODOS os produtos saíam
    calculadas sobre uma base menor. Compara com a soma crua de order_items,
    porque checar só "a linha aparece" passaria mesmo com a receita errada.
    """
    conn = abc_conn_com_anuncio_apagado
    cru = conn.execute(
        "SELECT ROUND(SUM(oi.quantity*oi.unit_price),2) FROM order_items oi "
        "JOIN orders o ON o.order_id = oi.order_id WHERE o.status='paid'"
    ).fetchone()[0]
    assert cru == pytest.approx(1000.0)

    df = abc_pareto(conn, "2026-07-01", "2026-08-01")

    assert list(df["sku"]) == ["MLB1", "MLB404", "MLB2"]
    assert df["receita"].sum() == pytest.approx(cru), "receita diverge da soma crua"
    # Fallback do título = o próprio SKU; quem está em cache mantém o real.
    por_sku = df.set_index("sku")
    assert por_sku.loc["MLB404", "titulo"] == "MLB404"
    assert por_sku.loc["MLB1", "titulo"] == "Produto 1"
    assert df["titulo"].notna().all()
    # Os percentuais são calculados sobre o total COMPLETO (1000, não 700).
    assert por_sku.loc["MLB1", "receita_pct"] == pytest.approx(60.0)
    assert por_sku.loc["MLB404", "receita_pct"] == pytest.approx(30.0)
    assert df.iloc[-1]["receita_acumulada_pct"] == pytest.approx(100.0)


_CAUDA_LONGA_CABECA = [5000.00, 2500.00, 1200.00, 800.00, 640.00]
_CAUDA_LONGA_ITEM = 29.90
_CAUDA_LONGA_N = 110


@pytest.fixture
def abc_conn_cauda_longa() -> sqlite3.Connection:
    """Catálogo grande, desenhado para EXPOR o erro acumulado de arredondamento.

    5 produtos "cabeça" com receitas distintas + 110 itens de cauda vendidos a
    R$ 29,90 cada (115 produtos, total R$ 13.429,00).

    Por que esta forma e não 4 produtos redondos: o bug era somar
    `receita_pct` já arredondado em 4 casas. Com receitas que dividem o total
    de forma exata o erro por linha é zero e o defeito não aparece; com
    receitas aleatórias os erros se cancelam (random walk). O que acumula
    desvio é um bloco grande de produtos cuja fração do total cai sempre do
    mesmo lado do arredondamento — exatamente a cauda longa de um catálogo
    real. Aqui o acumulado final dava 100,0053 pela fórmula antiga.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _seed_minimal_schema(conn)
    conn.execute("INSERT INTO categories_cache (category_id, name) VALUES ('CAT1', 'Cat Um')")

    receitas = list(_CAUDA_LONGA_CABECA) + [_CAUDA_LONGA_ITEM] * _CAUDA_LONGA_N
    for order_id, receita in enumerate(receitas, start=1):
        item_id = f"MLB{order_id:04d}"
        conn.execute(
            "INSERT INTO items_cache (item_id, title, category_id) VALUES (?, ?, 'CAT1')",
            (item_id, f"Produto {order_id}"),
        )
        conn.execute(
            "INSERT INTO orders (order_id, date_closed, status, total_amount, buyer_id) "
            "VALUES (?, '2026-07-10T10:00:00', 'paid', ?, 1001)",
            (order_id, receita),
        )
        conn.execute(
            "INSERT INTO order_items (order_id, item_id, quantity, unit_price) VALUES (?, ?, 1, ?)",
            (order_id, item_id, receita),
        )
    conn.commit()
    yield conn
    conn.close()


def test_abc_pareto_acumulada_fecha_em_100_em_catalogo_grande(
    abc_conn_cauda_longa: sqlite3.Connection,
) -> None:
    """O acumulado tem que FECHAR em 100, não "quase" 100.

    Regressão do erro de arredondamento acumulado: a fórmula antiga somava
    `receita_pct` já arredondado linha a linha e o último valor saía 100,0053
    neste catálogo. Como o eixo direito do Pareto é 0-100% por definição, um
    valor acima de 100 fazia o gráfico esticar o domínio e rotular o topo com
    decimais.
    """
    df = abc_pareto(abc_conn_cauda_longa, "2026-07-01", "2026-08-01")

    assert len(df) == len(_CAUDA_LONGA_CABECA) + _CAUDA_LONGA_N
    assert df.iloc[-1]["receita_acumulada_pct"] == pytest.approx(100.0, abs=0.001)
    # O acumulado nunca pode passar de 100: é uma fração do próprio total.
    assert df["receita_acumulada_pct"].max() <= 100.0


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
    # Fixture tem 6 buyers distintos.
    assert len(df) == 6
    assert df["buyer_id"].nunique() == 6


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


def test_rfm_buyer2_is_loyal(rfm_conn: sqlite3.Connection) -> None:
    """Buyer com 4 compras e gasto médio mas recente → f_score>=4 e m_score>=3 → Loyal.

    Scores realizados na fixture (janela 2026-05-01..2026-08-01):
      recency=22d → r_score=4, frequency=4 → f_score=4, monetary=1100 → m_score=3.
    Não ativa Champions (exige m_score>=4); primeira regra que casa é Loyal.
    """
    df = rfm_scores(rfm_conn, "2026-05-01", "2026-08-01")
    buyer2 = df.loc[df["buyer_id"] == 2].iloc[0]
    assert int(buyer2["f_score"]) >= 4, f"f_score esperado >=4, obtido {buyer2['f_score']}"
    assert int(buyer2["m_score"]) >= 3, f"m_score esperado >=3, obtido {buyer2['m_score']}"
    assert buyer2["segmento"] == "Loyal"


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


def test_rfm_others_segment_covers_mid_tier(rfm_conn: sqlite3.Connection) -> None:
    """Buyer com R/F/M mid-tier não casa nenhuma regra nomeada → Others."""
    df = rfm_scores(rfm_conn, "2026-05-01", "2026-08-01")
    buyer6_seg = df.loc[df["buyer_id"] == 6, "segmento"].iloc[0]
    assert buyer6_seg == "Others"


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


@pytest.fixture
def rfm_conn_cauda_longa() -> sqlite3.Connection:
    """Cenário que reproduz loja real: quase todo mundo compra uma vez só.

    Medido numa loja conectada de verdade (428 compradores, 6 meses): 398 tinham
    frequency=1 e 26 tinham frequency=2. Aqui: 40 buyers com 1 compra, 3 com 2 e
    1 com 3 — mesma forma de distribuição, escala reduzida.

    Janela: date_from='2026-05-01' até date_to='2026-08-01'.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _seed_minimal_schema(conn)
    conn.execute("INSERT INTO categories_cache (category_id, name) VALUES ('C', 'Cat')")
    conn.execute("INSERT INTO items_cache (item_id, title, category_id) VALUES ('X', 'X', 'C')")

    # (buyer_id, quantidade de compras) — cauda longa em frequency.
    perfis: list[tuple[int, int]] = [(b, 1) for b in range(1, 41)]
    perfis += [(41, 2), (42, 2), (43, 2), (44, 3)]

    oid = 0
    for buyer, n_compras in perfis:
        for i in range(n_compras):
            oid += 1
            # Espalha datas e valores para que recency e monetary tenham variedade;
            # o alvo do teste é frequency, que fica empatada de propósito.
            dia = 1 + ((buyer * 2 + i * 7) % 88)
            data = (pd.Timestamp("2026-05-01") + pd.Timedelta(days=dia)).strftime(
                "%Y-%m-%dT10:00:00"
            )
            total = 50.0 + (buyer % 11) * 37.0 + i * 13.0
            conn.execute(
                "INSERT INTO orders (order_id, date_closed, status, total_amount, buyer_id) "
                "VALUES (?, ?, 'paid', ?, ?)",
                (oid, data, total, buyer),
            )
            conn.execute(
                "INSERT INTO order_items (order_id, item_id, quantity, unit_price) "
                "VALUES (?, 'X', 1, ?)",
                (oid, total),
            )
    conn.commit()
    yield conn
    conn.close()


def test_rfm_empates_em_frequency_recebem_o_mesmo_score(
    rfm_conn_cauda_longa: sqlite3.Connection,
) -> None:
    """Valor de entrada igual → score igual. Vale para R, F e M.

    Regressão do bug de produção: `rank(method="first")` desempatava
    sequencialmente, então os 398 compradores com frequency=1 da loja real
    recebiam f_score de 1 a 5 — ruído puro alimentando o segmento RFM.
    """
    df = rfm_scores(rfm_conn_cauda_longa, "2026-05-01", "2026-08-01")
    assert not df.empty

    # A fixture precisa de fato ter empate pesado, senão o teste não prova nada.
    assert (df["frequency"] == 1).sum() >= 30

    for valor, score in [
        ("frequency", "f_score"),
        ("recency_dias", "r_score"),
        ("monetary", "m_score"),
    ]:
        nunique_por_valor = df.groupby(valor)[score].nunique()
        assert nunique_por_valor.max() == 1, (
            f"{valor} iguais produziram {score} diferentes: "
            f"{nunique_por_valor[nunique_por_valor > 1].to_dict()}"
        )


def test_rfm_cauda_longa_mantem_scores_entre_1_e_5(
    rfm_conn_cauda_longa: sqlite3.Connection,
) -> None:
    """Contrato antigo segue valendo mesmo com distribuição degenerada."""
    df = rfm_scores(rfm_conn_cauda_longa, "2026-05-01", "2026-08-01")
    for score in ["r_score", "f_score", "m_score"]:
        assert df[score].between(1, 5).all()
        assert df[score].dtype.kind == "i", f"{score} deveria ser int, é {df[score].dtype}"


@pytest.fixture
def cohort_conn() -> sqlite3.Connection:
    """Cenário controlado para cohort:
    - Produto P1 lança em jan/2026, vende em jan/fev/mar
    - Produto P2 lança em fev/2026, vende em fev/mar
    - Produto P3 lança em mar/2026, vende só em mar
    Não deve haver célula acima da diagonal (cada produto só vende após o lançamento).
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _seed_minimal_schema(conn)
    conn.execute("INSERT INTO categories_cache (category_id, name) VALUES ('C', 'Cat')")
    for pid in ["P1", "P2", "P3"]:
        conn.execute(
            "INSERT INTO items_cache (item_id, title, category_id) VALUES (?, ?, 'C')",
            (pid, f"Prod {pid}"),
        )
    orders: list[tuple[int, str, str, float]] = [
        # (order_id, date_closed, item_id, unit_price)
        (1, "2026-01-15T10:00:00", "P1", 100),
        (2, "2026-02-10T10:00:00", "P1", 200),
        (3, "2026-02-20T10:00:00", "P2", 300),
        (4, "2026-03-05T10:00:00", "P1", 150),
        (5, "2026-03-10T10:00:00", "P2", 350),
        (6, "2026-03-20T10:00:00", "P3", 400),
    ]
    for oid, date_closed, item_id, unit_price in orders:
        conn.execute(
            "INSERT INTO orders (order_id, date_closed, status, total_amount, buyer_id) "
            "VALUES (?, ?, 'paid', ?, 999)",
            (oid, date_closed, unit_price),
        )
        conn.execute(
            "INSERT INTO order_items (order_id, item_id, quantity, unit_price) VALUES (?, ?, 1, ?)",
            (oid, item_id, unit_price),
        )
    conn.commit()
    yield conn
    conn.close()


def test_cohort_returns_pivot_dataframe(cohort_conn: sqlite3.Connection) -> None:
    df = cohort_produto(cohort_conn, "2026-01-01", "2026-04-01")
    assert isinstance(df, pd.DataFrame)
    # Index = meses de lançamento; colunas = meses correntes.
    assert df.index.name == "mes_lancamento"
    # 3 cohorts (jan, fev, mar) e 3 meses correntes (jan, fev, mar).
    assert list(df.index) == ["2026-01", "2026-02", "2026-03"]
    assert list(df.columns) == ["2026-01", "2026-02", "2026-03"]


def test_cohort_upper_triangle_is_nan(cohort_conn: sqlite3.Connection) -> None:
    """Produto não vende antes de existir — células acima da diagonal são NaN."""
    df = cohort_produto(cohort_conn, "2026-01-01", "2026-04-01")
    # Cohort fev não pode ter valor em jan; cohort mar não pode em jan/fev.
    assert pd.isna(df.loc["2026-02", "2026-01"])
    assert pd.isna(df.loc["2026-03", "2026-01"])
    assert pd.isna(df.loc["2026-03", "2026-02"])


def test_cohort_diagonal_matches_launch_month_revenue(cohort_conn: sqlite3.Connection) -> None:
    """Célula (mes_lancamento=X, mes_corrente=X) = receita total do cohort em X."""
    df = cohort_produto(cohort_conn, "2026-01-01", "2026-04-01")
    # P1 lança em jan e vende 100 em jan → cohort_jan em jan = 100.
    assert df.loc["2026-01", "2026-01"] == pytest.approx(100)
    # P2 lança em fev com 300 → cohort_fev em fev = 300.
    assert df.loc["2026-02", "2026-02"] == pytest.approx(300)
    # P3 lança em mar com 400 → cohort_mar em mar = 400.
    assert df.loc["2026-03", "2026-03"] == pytest.approx(400)


def test_cohort_p1_receita_across_months(cohort_conn: sqlite3.Connection) -> None:
    """Cohort jan (só P1) tem 100 em jan, 200 em fev, 150 em mar."""
    df = cohort_produto(cohort_conn, "2026-01-01", "2026-04-01")
    assert df.loc["2026-01", "2026-01"] == pytest.approx(100)
    assert df.loc["2026-01", "2026-02"] == pytest.approx(200)
    assert df.loc["2026-01", "2026-03"] == pytest.approx(150)


def test_cohort_empty_window_returns_empty_df(cohort_conn: sqlite3.Connection) -> None:
    df = cohort_produto(cohort_conn, "2020-01-01", "2020-01-02")
    assert df.empty


# ---- RFM: cobertura de partição ----


@pytest.mark.parametrize("r", range(1, 6))
@pytest.mark.parametrize("f", range(1, 6))
@pytest.mark.parametrize("m", range(1, 6))
def test_assign_segment_returns_valid_label_for_all_combinations(r: int, f: int, m: int) -> None:
    """Cada uma das 125 combinações (r,f,m) mapeia para um segmento conhecido.

    Guarda contra `_assign_segment` devolver algo fora do vocabulário fixo se
    alguma regra for editada de forma inconsistente no futuro.
    """
    valid = {"Champions", "Loyal", "At Risk", "New", "Hibernating", "Others"}
    row = pd.Series({"r_score": r, "f_score": f, "m_score": m})
    assert _assign_segment(row) in valid

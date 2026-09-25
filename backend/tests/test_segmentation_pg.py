from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from backend.analytics.segmentation_pg import abc_pareto, cohort_produto, rfm_scores

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3::timestamptz, $4, $5, $6, $7, $8, '{}'::jsonb, now())
"""


async def _order(
    pool, seller_id, order_id, date_closed, total, fee=0.0, ship=0.0, status="paid", buyer_id=1001
):
    # asyncpg exige datetime real (nao str) para parametro usado com cast
    # ::timestamptz -- o protocolo binario nao faz esse parse.
    dt = datetime.fromisoformat(date_closed)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            _INSERT_ORDER, order_id, seller_id, dt, status, total, fee, ship, buyer_id
        )


async def _item(pool, seller_id, item_id, title, category_id="CAT1", category_name="Categoria 1"):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO categories_cache (seller_id, category_id, name, fetched_at) "
            "VALUES ($1,$2,$3,now()) ON CONFLICT DO NOTHING",
            seller_id,
            category_id,
            category_name,
        )
        await conn.execute(
            "INSERT INTO items_cache (seller_id, item_id, title, category_id, fetched_at) "
            "VALUES ($1,$2,$3,$4,now()) ON CONFLICT DO NOTHING",
            seller_id,
            item_id,
            title,
            category_id,
        )


async def _order_item(pool, seller_id, order_id, item_id, qty, unit_price):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO order_items (seller_id, order_id, item_id, quantity, unit_price) "
            "VALUES ($1,$2,$3,$4,$5)",
            seller_id,
            order_id,
            item_id,
            qty,
            unit_price,
        )


# ---------- abc_pareto ----------


async def test_abc_pareto_classifica_a_b_c_com_fronteira(pg_pool, test_seller):
    """4 produtos cobrindo as 3 classes, com um produto cruzando a fronteira
    de 80% dentro da propria contribuicao (linha inteira vai pra classe
    superior, nao e dividida)."""
    _, sid = test_seller
    produtos = [
        ("MLB1", "Produto 1", 750.0),
        ("MLB2", "Produto 2", 100.0),
        ("MLB3", "Produto 3", 100.0),
        ("MLB4", "Produto 4", 50.0),
    ]
    for i, (item_id, title, receita) in enumerate(produtos, start=1):
        await _item(pg_pool, sid, item_id, title)
        await _order(pg_pool, sid, i, "2026-07-15T10:00:00+00:00", receita)
        await _order_item(pg_pool, sid, i, item_id, 1, receita)

    df = await abc_pareto(pg_pool, sid, "2026-07-01", "2026-08-01")

    assert list(df["sku"]) == ["MLB1", "MLB2", "MLB3", "MLB4"]
    assert df.iloc[0]["receita_acumulada_pct"] == pytest.approx(75.0)
    assert df.iloc[1]["receita_acumulada_pct"] == pytest.approx(85.0)
    assert df.iloc[2]["receita_acumulada_pct"] == pytest.approx(95.0)
    assert df.iloc[3]["receita_acumulada_pct"] == pytest.approx(100.0)
    assert list(df["classe"]) == ["A", "B", "B", "C"]


async def test_abc_pareto_isola_por_seller(pg_pool, test_seller, outro_seller):
    _, sid = test_seller
    _, outro = outro_seller
    await _item(pg_pool, outro, "MLB9", "Do outro")
    await _order(pg_pool, outro, 1, "2026-07-15T10:00:00+00:00", 999.0)
    await _order_item(pg_pool, outro, 1, "MLB9", 1, 999.0)

    await _item(pg_pool, sid, "MLB1", "Produto 1")
    await _order(pg_pool, sid, 1, "2026-07-15T10:00:00+00:00", 100.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 1, 100.0)

    df = await abc_pareto(pg_pool, sid, "2026-07-01", "2026-08-01")
    assert list(df["sku"]) == ["MLB1"]
    assert df.iloc[0]["receita"] == pytest.approx(100.0)


async def test_abc_pareto_nao_infla_com_item_compartilhado(pg_pool, test_seller, outro_seller):
    """Fan-out cross-tenant: mesmo item_id e mesmo order_id nos dois sellers.

    Se o JOIN com items_cache perder o `seller_id`, a linha de order_items
    do seller de teste casa com o items_cache de AMBOS os sellers e a
    receita multiplica silenciosamente.
    """
    _, sid = test_seller
    _, outro = outro_seller
    for s in (sid, outro):
        await _item(pg_pool, s, "MLB1", "Produto A")
        await _order(pg_pool, s, 1, "2026-07-15T10:00:00+00:00", 100.0)
        await _order_item(pg_pool, s, 1, "MLB1", 1, 100.0)

    df = await abc_pareto(pg_pool, sid, "2026-07-01", "2026-08-01")
    assert len(df) == 1, f"fan-out: esperava 1 linha, veio {len(df)}"
    assert df.iloc[0]["receita"] == pytest.approx(100.0), "receita inflada por fan-out"


async def test_abc_pareto_vazio_tem_as_colunas_certas(pg_pool, test_seller):
    _, sid = test_seller
    df = await abc_pareto(pg_pool, sid, "2026-01-01", "2026-01-02")
    assert df.empty
    assert list(df.columns) == [
        "sku",
        "titulo",
        "receita",
        "receita_pct",
        "receita_acumulada_pct",
        "classe",
    ]


async def test_abc_pareto_paridade_com_a_versao_sqlite(pg_pool, test_seller):
    """Mesmos dados nos dois bancos tem que dar os mesmos numeros.

    Sem empates de receita (ORDER BY sem desempate no original), pra nao
    depender do criterio de desempate divergente da versao Postgres.
    """
    from src.segmentation import abc_pareto as abc_pareto_sqlite
    from src.storage import connect as sqlite_connect
    from src.storage import upsert_item_cache, upsert_order

    _, sid = test_seller
    itens = [
        ("MLB1", "Produto 1", "CAT1"),
        ("MLB2", "Produto 2", "CAT1"),
        ("MLB3", "Produto 3", "CAT1"),
    ]
    pedidos = [
        (1, "2026-07-10T10:00:00+00:00", [("MLB1", 1, 500.0)]),
        (2, "2026-07-15T10:00:00+00:00", [("MLB2", 1, 300.0)]),
        (3, "2026-07-20T10:00:00+00:00", [("MLB3", 1, 200.0)]),
    ]

    sconn = sqlite_connect(":memory:")
    try:
        for item_id, title, category_id in itens:
            upsert_item_cache(sconn, item_id, title, category_id)
        for order_id, date_closed, items in pedidos:
            upsert_order(
                sconn,
                {
                    "order_id": order_id,
                    "date_closed": date_closed,
                    "status": "paid",
                    "total_amount": sum(q * p for _, q, p in items),
                    "marketplace_fee": 0.0,
                    "shipping_cost": 0.0,
                    "buyer_id": 1001,
                    "raw_json": "{}",
                    "items": [
                        {"item_id": item_id, "quantity": qty, "unit_price": price}
                        for item_id, qty, price in items
                    ],
                },
            )
        sconn.commit()
        esperado = abc_pareto_sqlite(sconn, "2026-07-01", "2026-08-01")
    finally:
        sconn.close()

    for item_id, title, category_id in itens:
        await _item(pg_pool, sid, item_id, title, category_id)
    for order_id, date_closed, items in pedidos:
        total = sum(q * p for _, q, p in items)
        await _order(pg_pool, sid, order_id, date_closed, total)
        for item_id, qty, price in items:
            await _order_item(pg_pool, sid, order_id, item_id, qty, price)
    obtido = await abc_pareto(pg_pool, sid, "2026-07-01", "2026-08-01")

    pd.testing.assert_frame_equal(
        esperado.reset_index(drop=True),
        obtido.reset_index(drop=True),
        check_dtype=False,
        atol=1e-6,
    )


# ---------- rfm_scores ----------


async def _buyer_orders(pool, seller_id, buyer_id, order_id_start, amounts, last_date, step_days=1):
    """Insere `len(amounts)` pedidos pro comprador, o ultimo na data `last_date`
    e os demais em dias anteriores (todos dentro da janela do teste)."""
    from datetime import timedelta

    last_dt = datetime.fromisoformat(last_date)
    n = len(amounts)
    for i, amount in enumerate(amounts):
        offset = (n - 1 - i) * step_days
        dt = last_dt - timedelta(days=offset)
        await _order(pool, seller_id, order_id_start + i, dt.isoformat(), amount, buyer_id=buyer_id)


async def test_rfm_scores_caminho_feliz_com_recencias_variadas(pg_pool, test_seller):
    """5 compradores com recencia/frequencia/monetary distintos o bastante
    pra exercitar os 5 quintis, incluindo um que comprou no mesmo dia (data)
    de date_to e outro semanas antes."""
    _, sid = test_seller
    # date_to com horario != meia-noite pra permitir um pedido "no mesmo dia"
    # de date_to sem violar o corte exclusivo (< date_to).
    date_to = "2026-08-01T23:59:59+00:00"
    # Recuado o bastante pra caber todos os pedidos do comprador com mais
    # frequencia (5 pedidos, 1/dia, terminando em 07-02) dentro da janela.
    date_from = "2026-06-20"

    await _buyer_orders(pg_pool, sid, 1001, 100, [50.0], "2026-08-01T10:00:00+00:00")  # recency 0
    await _buyer_orders(
        pg_pool, sid, 1002, 200, [80.0, 70.0], "2026-07-25T09:00:00+00:00"
    )  # recency 7
    await _buyer_orders(
        pg_pool, sid, 1003, 300, [100.0, 100.0, 100.0], "2026-07-15T09:00:00+00:00"
    )  # recency 17
    await _buyer_orders(
        pg_pool, sid, 1004, 400, [120.0] * 4, "2026-07-08T09:00:00+00:00"
    )  # recency 24
    await _buyer_orders(
        pg_pool, sid, 1005, 500, [120.0] * 5, "2026-07-02T09:00:00+00:00"
    )  # recency 30

    df = await rfm_scores(pg_pool, sid, date_from, date_to)

    assert list(df.columns) == [
        "buyer_id",
        "recency_dias",
        "frequency",
        "monetary",
        "r_score",
        "f_score",
        "m_score",
        "segmento",
    ]
    assert len(df) == 5

    by_buyer = df.set_index("buyer_id")
    assert by_buyer.loc[1001, "recency_dias"] == 0
    assert by_buyer.loc[1002, "recency_dias"] == 7
    assert by_buyer.loc[1003, "recency_dias"] == 17
    assert by_buyer.loc[1004, "recency_dias"] == 24
    assert by_buyer.loc[1005, "recency_dias"] == 30

    assert by_buyer.loc[1001, "frequency"] == 1
    assert by_buyer.loc[1005, "frequency"] == 5
    assert by_buyer.loc[1005, "monetary"] == pytest.approx(600.0)

    # recency menor = melhor -> r_score mais alto para o comprador mais recente.
    assert by_buyer.loc[1001, "r_score"] > by_buyer.loc[1005, "r_score"]
    # frequency/monetary maiores -> f_score/m_score mais altos.
    assert by_buyer.loc[1005, "f_score"] > by_buyer.loc[1001, "f_score"]
    assert by_buyer.loc[1005, "m_score"] > by_buyer.loc[1001, "m_score"]

    assert set(df["segmento"]) <= {
        "Champions",
        "Loyal",
        "At Risk",
        "New",
        "Hibernating",
        "Others",
    }


async def test_rfm_scores_isola_por_seller(pg_pool, test_seller, outro_seller):
    _, sid = test_seller
    _, outro = outro_seller
    await _order(pg_pool, outro, 1, "2026-07-25T10:00:00+00:00", 999.0, buyer_id=9999)
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 50.0, buyer_id=1001)

    df = await rfm_scores(pg_pool, sid, "2026-07-01", "2026-08-01")
    assert list(df["buyer_id"]) == [1001]


async def test_rfm_scores_nao_mistura_comprador_entre_sellers(pg_pool, test_seller, outro_seller):
    """Fan-out cross-tenant (variante sem JOIN): buyer_id e um id global do ML
    -- o mesmo comprador pode comprar de varios sellers. rfm_scores nao tem
    JOIN pra duplicar linhas, mas perder o filtro `seller_id` misturaria os
    pedidos desse comprador entre tenants, inflando frequency/monetary do
    mesmo jeito que um fan-out de JOIN infla receita.
    """
    _, sid = test_seller
    _, outro = outro_seller

    await _buyer_orders(pg_pool, sid, 2001, 10, [60.0, 40.0], "2026-07-20T10:00:00+00:00")
    await _buyer_orders(
        pg_pool, outro, 2001, 20, [999.0, 999.0, 999.0], "2026-07-20T10:00:00+00:00"
    )

    df = await rfm_scores(pg_pool, sid, "2026-07-01", "2026-08-01")
    row = df[df["buyer_id"] == 2001].iloc[0]
    assert row["frequency"] == 2, "frequency inflada por dados do outro seller"
    assert row["monetary"] == pytest.approx(100.0), "monetary inflado por dados do outro seller"


async def test_rfm_scores_vazio_tem_as_colunas_certas(pg_pool, test_seller):
    _, sid = test_seller
    df = await rfm_scores(pg_pool, sid, "2026-01-01", "2026-01-02")
    assert df.empty
    assert list(df.columns) == [
        "buyer_id",
        "recency_dias",
        "frequency",
        "monetary",
        "r_score",
        "f_score",
        "m_score",
        "segmento",
    ]


async def test_rfm_scores_paridade_com_a_versao_sqlite(pg_pool, test_seller):
    """Pega o bug de truncamento do calculo de recency (Step 3): uma compra
    as 14:30 do dia anterior tem que dar 1 dia de recencia (truncado pra
    data), nao 0 (se a diferenca fosse calculada sobre o timestamp cru).
    """
    from src.segmentation import rfm_scores as rfm_sqlite
    from src.storage import connect as sqlite_connect
    from src.storage import upsert_order

    _, sid = test_seller
    pedidos = [
        (1, "2026-07-31T14:30:00+00:00", 80.0, 1001),
        (2, "2026-07-05T09:00:00+00:00", 45.5, 1002),
        (3, "2026-07-20T18:00:00+00:00", 60.0, 1003),
    ]

    sconn = sqlite_connect(":memory:")
    try:
        for order_id, date_closed, total, buyer_id in pedidos:
            upsert_order(
                sconn,
                {
                    "order_id": order_id,
                    "date_closed": date_closed,
                    "status": "paid",
                    "total_amount": total,
                    "marketplace_fee": 0.0,
                    "shipping_cost": 0.0,
                    "buyer_id": buyer_id,
                    "raw_json": "{}",
                    "items": [],
                },
            )
        sconn.commit()
        esperado = rfm_sqlite(sconn, "2026-07-01", "2026-08-01")
    finally:
        sconn.close()

    for order_id, date_closed, total, buyer_id in pedidos:
        await _order(pg_pool, sid, order_id, date_closed, total, buyer_id=buyer_id)
    obtido = await rfm_scores(pg_pool, sid, "2026-07-01", "2026-08-01")

    esperado = esperado.sort_values("buyer_id").reset_index(drop=True)
    obtido = obtido.sort_values("buyer_id").reset_index(drop=True)

    pd.testing.assert_frame_equal(
        esperado,
        obtido,
        check_dtype=False,
        atol=1e-6,
    )

    # Trava explicita do Step 3: buyer 1001 comprou as 14:30 de 07-31,
    # date_to e 08-01 -> recencia tem que ser 1 dia, nao 0.
    assert int(obtido.loc[obtido["buyer_id"] == 1001, "recency_dias"].iloc[0]) == 1


# ---------- cohort_produto ----------


async def test_cohort_produto_lancamento_fora_da_janela(pg_pool, test_seller):
    """Produto lancado antes da janela e vendido dentro dela: o mes de
    lancamento tem que vir do banco inteiro, nao so da janela."""
    _, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto 1")
    await _item(pg_pool, sid, "MLB2", "Produto 2")

    # MLB1: lancado em junho (fora da janela), vendido em julho e agosto.
    await _order(pg_pool, sid, 1, "2026-06-15T10:00:00+00:00", 100.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 1, 100.0)
    await _order(pg_pool, sid, 2, "2026-07-10T09:00:00+00:00", 100.0)
    await _order_item(pg_pool, sid, 2, "MLB1", 1, 100.0)
    await _order(pg_pool, sid, 3, "2026-08-05T09:00:00+00:00", 60.0)
    await _order_item(pg_pool, sid, 3, "MLB1", 1, 60.0)

    # MLB2: lancado dentro da janela (julho), sem venda em agosto.
    await _order(pg_pool, sid, 4, "2026-07-20T10:00:00+00:00", 70.0)
    await _order_item(pg_pool, sid, 4, "MLB2", 1, 70.0)

    pivot = await cohort_produto(pg_pool, sid, "2026-07-01", "2026-09-01")

    assert list(pivot.index) == ["2026-06", "2026-07"]
    assert list(pivot.columns) == ["2026-07", "2026-08"]
    assert pivot.loc["2026-06", "2026-07"] == pytest.approx(100.0)
    assert pivot.loc["2026-06", "2026-08"] == pytest.approx(60.0)
    assert pivot.loc["2026-07", "2026-07"] == pytest.approx(70.0)
    assert pd.isna(pivot.loc["2026-07", "2026-08"])


async def test_cohort_produto_isola_por_seller(pg_pool, test_seller, outro_seller):
    _, sid = test_seller
    _, outro = outro_seller
    await _item(pg_pool, outro, "MLB9", "Do outro")
    await _order(pg_pool, outro, 1, "2025-01-01T10:00:00+00:00", 999.0)
    await _order_item(pg_pool, outro, 1, "MLB9", 1, 999.0)

    await _item(pg_pool, sid, "MLB1", "Produto 1")
    await _order(pg_pool, sid, 1, "2026-07-10T10:00:00+00:00", 100.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 1, 100.0)

    pivot = await cohort_produto(pg_pool, sid, "2026-07-01", "2026-08-01")
    assert list(pivot.index) == ["2026-07"]
    assert list(pivot.columns) == ["2026-07"]
    assert pivot.loc["2026-07", "2026-07"] == pytest.approx(100.0)


async def test_cohort_produto_nao_infla_com_item_e_pedido_compartilhados(
    pg_pool, test_seller, outro_seller
):
    """Fan-out cross-tenant: mesmo item_id e mesmo order_id (colisao valida,
    pois a PK de orders e (seller_id, order_id)) nos dois sellers, mesma data
    (dentro da janela, pra nao ser filtrada). Se o JOIN com orders perder o
    `seller_id`, a linha de order_items do seller de teste casa tambem com o
    pedido do outro seller e a receita do cohort multiplica.
    """
    _, sid = test_seller
    _, outro = outro_seller
    for s in (sid, outro):
        await _item(pg_pool, s, "MLB1", "Produto A")
        await _order(pg_pool, s, 1, "2026-07-10T10:00:00+00:00", 100.0)
        await _order_item(pg_pool, s, 1, "MLB1", 1, 100.0)

    pivot = await cohort_produto(pg_pool, sid, "2026-07-01", "2026-08-01")
    assert pivot.shape == (1, 1), f"fan-out: esperava 1x1, veio {pivot.shape}"
    assert pivot.iloc[0, 0] == pytest.approx(100.0), "receita inflada por fan-out"


async def test_cohort_produto_vazio(pg_pool, test_seller):
    _, sid = test_seller
    pivot = await cohort_produto(pg_pool, sid, "2026-01-01", "2026-01-02")
    assert pivot.empty


async def test_cohort_produto_agrupa_mes_em_utc_na_virada_do_dia(pg_pool, test_seller):
    """Pedido as 02:00Z do dia 1 do mes tem que cair no mes correto (agosto),
    nao no mes anterior -- cobre o `AT TIME ZONE 'UTC'` no agrupamento
    mensal (to_char sobre timestamptz usa o fuso da SESSAO sem ele)."""
    _, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto 1")
    await _order(pg_pool, sid, 1, "2026-08-01T02:00:00+00:00", 90.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 1, 90.0)

    pivot = await cohort_produto(pg_pool, sid, "2026-08-01", "2026-08-02")

    assert list(pivot.index) == ["2026-08"]
    assert list(pivot.columns) == ["2026-08"]
    assert pivot.loc["2026-08", "2026-08"] == pytest.approx(90.0)


async def test_cohort_independe_do_fuso_da_sessao(pg_pool, pg_pool_fuso_nao_utc, test_seller):
    """O agrupamento por MES nao pode mudar com o TimeZone da sessao.

    Protege o `AT TIME ZONE 'UTC'` das duas queries do cohort. Sem ele, um
    pedido de 1o de agosto as 02:00Z e contabilizado em JULHO quando a sessao
    esta em America/Sao_Paulo (UTC-3) — o cohort inteiro desloca de mes.
    Verificado por mutacao: sem este teste, remover o AT TIME ZONE passa
    despercebido, porque o pool padrao dos testes ja fixa UTC.
    """
    _, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto A", "CAT1", "Categoria 1")
    # 02:00Z do dia 1o = 23:00 do ultimo dia de julho em Sao_Paulo.
    await _order(pg_pool, sid, 1, "2026-08-01T02:00:00+00:00", 100.0, 0.0, 0.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 1, 100.0)

    em_utc = await cohort_produto(pg_pool, sid, "2026-08-01", "2026-09-01")
    em_sp = await cohort_produto(pg_pool_fuso_nao_utc, sid, "2026-08-01", "2026-09-01")

    pd.testing.assert_frame_equal(em_utc, em_sp, check_dtype=False, atol=1e-6)
    assert "2026-08" in em_utc.index

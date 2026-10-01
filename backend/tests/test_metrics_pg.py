from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from backend.analytics.metrics_pg import SEM_CATEGORIA, fluxo_financeiro, top_produtos

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3::timestamptz, $4, $5, $6, $7, $8, '{}'::jsonb, now())
"""


async def _order(
    pool, seller_id, order_id, date_closed, total, fee, ship, status="paid", buyer_id=1001
):
    # asyncpg 0.31 exige datetime real (nao str) para um parametro usado com
    # cast ::timestamptz no SQL -- o protocolo binario nao faz esse parse.
    dt = datetime.fromisoformat(date_closed)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            _INSERT_ORDER, order_id, seller_id, dt, status, total, fee, ship, buyer_id
        )


async def _item(pool, seller_id, item_id, title, category_id, category_name):
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


# ---------- fluxo_financeiro ----------


async def test_fluxo_agrega_por_dia(pg_pool, test_seller):
    _, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 10.0, 5.0)
    await _order(pg_pool, sid, 2, "2026-07-25T15:00:00+00:00", 50.0, 5.0, 2.5)
    df = await fluxo_financeiro(pg_pool, sid, "2026-07-25", "2026-07-26")
    assert len(df) == 1
    r = df.iloc[0]
    assert r["date"] == "2026-07-25"
    assert r["receita_bruta"] == pytest.approx(150.0)
    assert r["taxas_ml"] == pytest.approx(15.0)
    assert r["frete"] == pytest.approx(7.5)
    assert r["margem_contribuicao"] == pytest.approx(150.0 - 15.0 - 7.5, abs=0.01)


async def test_fluxo_ignora_nao_pagos(pg_pool, test_seller):
    _, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 10.0, 5.0)
    await _order(pg_pool, sid, 2, "2026-07-25T11:00:00+00:00", 999.0, 0.0, 0.0, status="cancelled")
    df = await fluxo_financeiro(pg_pool, sid, "2026-07-25", "2026-07-26")
    assert df.iloc[0]["receita_bruta"] == pytest.approx(100.0)


async def test_fluxo_isola_por_seller(pg_pool, test_seller, outro_seller):
    _, sid = test_seller
    _, outro = outro_seller
    await _order(pg_pool, outro, 1, "2026-07-25T10:00:00+00:00", 999.0, 0.0, 0.0)
    df = await fluxo_financeiro(pg_pool, sid, "2026-07-25", "2026-07-26")
    assert df.empty


async def test_fluxo_respeita_bordas_da_janela_em_utc(pg_pool, test_seller):
    """date_to e EXCLUSIVO e o corte e em UTC, nao no fuso local."""
    _, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-07-24T23:59:00+00:00", 10.0, 0.0, 0.0)  # fora (antes)
    await _order(pg_pool, sid, 2, "2026-07-25T00:00:00+00:00", 20.0, 0.0, 0.0)  # dentro
    await _order(pg_pool, sid, 3, "2026-07-25T23:59:00+00:00", 30.0, 0.0, 0.0)  # dentro
    await _order(pg_pool, sid, 4, "2026-07-26T00:00:00+00:00", 40.0, 0.0, 0.0)  # fora (depois)
    df = await fluxo_financeiro(pg_pool, sid, "2026-07-25", "2026-07-26")
    assert len(df) == 1
    assert df.iloc[0]["receita_bruta"] == pytest.approx(50.0)


async def test_fluxo_margem_e_receita_menos_taxas_menos_frete(pg_pool, test_seller):
    """Margem de contribuicao = receita - taxas ML - frete, ate o centavo.

    Valores com centavos que nao se cancelam, pra `.round(2)` ter o que
    arredondar — fixture redonda deixaria a formula errada passar.

    2026-06-01: 1234,567 - 185,185 - 27,333 = 1022,049 -> 1.022,05
    2026-06-02:  987,654 -  98,765 -  0,041 =  888,848 ->   888,85
    """
    _, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-06-01T08:15:00+00:00", 1234.567, 185.185, 27.333)
    await _order(pg_pool, sid, 2, "2026-06-02T19:45:00+00:00", 987.654, 98.765, 0.041)
    df = await fluxo_financeiro(pg_pool, sid, "2026-06-01", "2026-06-03")

    esperado = (df["receita_bruta"] - df["taxas_ml"] - df["frete"]).round(2)
    pd.testing.assert_series_equal(df["margem_contribuicao"], esperado, check_names=False)

    por_dia = df.set_index("date")["margem_contribuicao"]
    assert por_dia.loc["2026-06-01"] == pytest.approx(1022.05, abs=0.005)
    assert por_dia.loc["2026-06-02"] == pytest.approx(888.85, abs=0.005)


async def test_fluxo_margem_nao_desconta_custo_estimado(pg_pool, test_seller):
    """Nenhum percentual de custo sai da margem.

    A assercao compara contra o valor que a formula ANTIGA (com 55% de COGS)
    daria, em vez de um limiar de razao arbitrario: e a reintroducao daquele
    percentual que este teste tem que pegar, e nada mais.
    """
    _, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-06-01T08:15:00+00:00", 1234.567, 185.185, 27.333)
    df = await fluxo_financeiro(pg_pool, sid, "2026-06-01", "2026-06-02")
    r = df.iloc[0]

    receita, taxas, frete = r["receita_bruta"], r["taxas_ml"], r["frete"]
    com_cogs_55 = receita - taxas - frete - round(receita * 0.55, 2)
    assert com_cogs_55 == pytest.approx(343.04, abs=0.01)  # o numero que a tela mostrava

    assert r["margem_contribuicao"] == pytest.approx(receita - taxas - frete, abs=0.01)
    assert r["margem_contribuicao"] > com_cogs_55
    assert r["margem_contribuicao"] != pytest.approx(com_cogs_55, abs=1.0)


async def test_fluxo_vazio_tem_as_colunas_certas(pg_pool, test_seller):
    """Conjunto de colunas EXATO, nos dois caminhos (vazio e com dados).

    A igualdade de lista, e nao um subset, e o ponto: um `custo_estimado`
    reintroduzido quebra aqui em vez de voltar silenciosamente pra tela.
    """
    _, sid = test_seller
    df = await fluxo_financeiro(pg_pool, sid, "2026-01-01", "2026-01-02")
    assert df.empty
    assert list(df.columns) == [
        "date",
        "receita_bruta",
        "taxas_ml",
        "frete",
        "margem_contribuicao",
    ]

    await _order(pg_pool, sid, 1, "2026-01-01T10:00:00+00:00", 100.0, 10.0, 5.0)
    com_dados = await fluxo_financeiro(pg_pool, sid, "2026-01-01", "2026-01-02")
    assert list(com_dados.columns) == list(df.columns)


async def test_fluxo_colunas_numericas_sao_float(pg_pool, test_seller):
    """numeric do Postgres volta como Decimal no asyncpg — tem que virar float."""
    _, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 10.0, 5.0)
    df = await fluxo_financeiro(pg_pool, sid, "2026-07-25", "2026-07-26")
    for col in ["receita_bruta", "taxas_ml", "frete", "margem_contribuicao"]:
        assert df[col].dtype.kind == "f", f"{col} deveria ser float, veio {df[col].dtype}"


async def test_fluxo_paridade_com_a_versao_sqlite(pg_pool, test_seller):
    """O porte tem que dar os MESMOS numeros que o original em SQLite.

    E o unico teste que pega erro sutil de traducao de dialeto (agregacao,
    arredondamento, fuso). Os horarios perto da meia-noite UTC sao de proposito.
    """
    from src.metrics import fluxo_financeiro as fluxo_sqlite
    from src.storage import connect as sqlite_connect
    from src.storage import upsert_order

    _, sid = test_seller
    pedidos = [
        (1, "2026-07-25T10:00:00+00:00", 100.0, 10.0, 5.0),
        (2, "2026-07-25T23:30:00+00:00", 50.0, 5.0, 2.5),
        (3, "2026-07-26T00:30:00+00:00", 70.0, 7.0, 3.5),
        (4, "2026-07-26T12:00:00+00:00", 33.33, 3.33, 1.11),
    ]

    sconn = sqlite_connect(":memory:")
    try:
        for oid, dt, total, fee, ship in pedidos:
            upsert_order(
                sconn,
                {
                    "order_id": oid,
                    "date_closed": dt,
                    "status": "paid",
                    "total_amount": total,
                    "marketplace_fee": fee,
                    "shipping_cost": ship,
                    "buyer_id": 1001,
                    "raw_json": "{}",
                    "items": [],
                },
            )
        sconn.commit()
        esperado = fluxo_sqlite(sconn, "2026-07-25", "2026-07-27")
    finally:
        sconn.close()

    for oid, dt, total, fee, ship in pedidos:
        await _order(pg_pool, sid, oid, dt, total, fee, ship)
    obtido = await fluxo_financeiro(pg_pool, sid, "2026-07-25", "2026-07-27")

    pd.testing.assert_frame_equal(
        esperado.reset_index(drop=True),
        obtido.reset_index(drop=True),
        check_dtype=False,
        atol=1e-6,
    )


# ---------- top_produtos ----------


async def test_top_produtos_ranqueia_por_receita(pg_pool, test_seller):
    _, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto A", "CAT1", "Categoria 1")
    await _item(pg_pool, sid, "MLB2", "Produto B", "CAT1", "Categoria 1")
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 300.0, 0.0, 0.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 2, 50.0)  # 100
    await _order_item(pg_pool, sid, 1, "MLB2", 1, 200.0)  # 200

    res = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-26")
    prod = res["produtos"]
    assert list(prod["item_id"]) == ["MLB2", "MLB1"]
    assert prod.iloc[0]["receita"] == pytest.approx(200.0)
    assert prod.iloc[0]["unidades"] == 1
    assert prod.iloc[0]["title"] == "Produto B"
    assert prod.iloc[0]["category_name"] == "Categoria 1"

    cat = res["categorias"]
    assert len(cat) == 1
    assert cat.iloc[0]["receita"] == pytest.approx(300.0)
    assert cat.iloc[0]["unidades"] == 3


async def test_top_produtos_respeita_limite_n(pg_pool, test_seller):
    _, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 600.0, 0.0, 0.0)
    for i in range(1, 4):
        await _item(pg_pool, sid, f"MLB{i}", f"Produto {i}", "CAT1", "Categoria 1")
        await _order_item(pg_pool, sid, 1, f"MLB{i}", 1, 100.0 * i)
    res = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-26", n=2)
    assert len(res["produtos"]) == 2
    assert list(res["produtos"]["item_id"]) == ["MLB3", "MLB2"]


async def test_top_produtos_isola_por_seller(pg_pool, test_seller, outro_seller):
    _, sid = test_seller
    _, outro = outro_seller
    await _item(pg_pool, outro, "MLB9", "Do outro", "CAT9", "Cat do outro")
    await _order(pg_pool, outro, 1, "2026-07-25T10:00:00+00:00", 999.0, 0.0, 0.0)
    await _order_item(pg_pool, outro, 1, "MLB9", 1, 999.0)
    res = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-26")
    assert res["produtos"].empty
    assert res["categorias"].empty


async def test_top_produtos_vazio_tem_as_colunas_certas(pg_pool, test_seller):
    _, sid = test_seller
    res = await top_produtos(pg_pool, sid, "2026-01-01", "2026-01-02")
    assert list(res["produtos"].columns) == [
        "item_id",
        "title",
        "category_name",
        "unidades",
        "receita",
    ]
    assert list(res["categorias"].columns) == [
        "category_id",
        "category_name",
        "unidades",
        "receita",
    ]


async def test_top_produtos_nao_infla_com_categoria_compartilhada(
    pg_pool, test_seller, outro_seller
):
    """Fan-out cross-tenant: category_id do ML e GLOBAL (ex: MLB1234), entao
    varios sellers tem linha com o MESMO category_id em categories_cache.

    Se um JOIN perder o `seller_id`, cada linha de order_items casa N vezes
    (N = sellers na mesma categoria) e a receita MULTIPLICA silenciosamente.
    O teste de isolamento nao pega isso porque usa category_id diferente
    entre os sellers — sem colisao, nao ha fan-out pra observar.
    """
    _, sid = test_seller
    _, outro = outro_seller

    # MESMO category_id e MESMO item_id nos dois sellers (cenario real do ML),
    # e MESMO order_id, pra tambem cobrir o join com orders.
    for s in (sid, outro):
        await _item(pg_pool, s, "MLB1", "Produto A", "MLB1234", "Eletronicos")
        await _order(pg_pool, s, 1, "2026-07-25T10:00:00+00:00", 100.0, 0.0, 0.0)
        await _order_item(pg_pool, s, 1, "MLB1", 1, 100.0)

    res = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-26")

    prod = res["produtos"]
    assert len(prod) == 1, f"fan-out: esperava 1 linha, veio {len(prod)}"
    assert prod.iloc[0]["receita"] == pytest.approx(100.0), "receita inflada por fan-out"
    assert prod.iloc[0]["unidades"] == 1, "unidades infladas por fan-out"

    cat = res["categorias"]
    assert len(cat) == 1, f"fan-out: esperava 1 categoria, veio {len(cat)}"
    assert cat.iloc[0]["receita"] == pytest.approx(100.0), "receita de categoria inflada"


async def test_top_produtos_desempate_estavel_por_item_id(pg_pool, test_seller):
    """Empate de receita tem que ter desempate deterministico (por item_id).

    Sem `ORDER BY receita DESC, item_id`, a ordem entre linhas empatadas nao
    e garantida pelo Postgres — com LIMIT, o "produto top" podia alternar
    entre recarregamentos. MLB1 < MLB2 lexicograficamente, entao com n=1
    o resultado tem que ser sempre MLB1.
    """
    _, sid = test_seller
    await _item(pg_pool, sid, "MLB2", "Produto B", "CAT1", "Categoria 1")
    await _item(pg_pool, sid, "MLB1", "Produto A", "CAT1", "Categoria 1")
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 200.0, 0.0, 0.0)
    await _order_item(pg_pool, sid, 1, "MLB2", 1, 100.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 1, 100.0)

    for _ in range(5):
        res = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-26", n=1)
        assert list(res["produtos"]["item_id"]) == ["MLB1"]


async def _receita_bruta_dos_itens(pool, seller_id, date_from, date_to):
    """Verdade-base: soma crua de quantity * unit_price dos itens de pedidos
    pagos na janela, SEM passar por items_cache nem categories_cache."""
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT SUM(oi.quantity * oi.unit_price) FROM order_items oi "
            "JOIN orders o ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id "
            "WHERE oi.seller_id = $1 AND o.status = 'paid' "
            "AND o.date_closed >= $2 AND o.date_closed < $3",
            seller_id,
            datetime.fromisoformat(date_from).replace(tzinfo=UTC),
            datetime.fromisoformat(date_to).replace(tzinfo=UTC),
        )
    return float(total)


async def test_top_produtos_mantem_item_sem_cache_e_a_receita_total(pg_pool, test_seller):
    """Anuncio apagado no ML devolve 404 na ingestao e nunca entra em
    items_cache — mas a venda foi real. Os INNER JOINs faziam o item sumir do
    ranking junto com a receita, e a tela Produtos divergia da Executive.

    Compara o TOTAL com a soma crua de order_items: checar so "a linha
    aparece" passaria mesmo com a receita errada.
    """
    _, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto em cache", "CAT1", "Categoria 1")
    # MLB2 e MLB3 nao tem items_cache: anuncios apagados.
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 450.55, 0.0, 0.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 2, 50.0)  # 100,00
    await _order_item(pg_pool, sid, 1, "MLB2", 3, 100.0)  # 300,00
    await _order_item(pg_pool, sid, 1, "MLB3", 1, 50.55)  # 50,55

    res = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-26", n=100)
    prod = res["produtos"]

    assert set(prod["item_id"]) == {"MLB1", "MLB2", "MLB3"}, "item sem cache sumiu do ranking"
    esperado = await _receita_bruta_dos_itens(pg_pool, sid, "2026-07-25", "2026-07-26")
    assert esperado == pytest.approx(450.55)
    assert prod["receita"].sum() == pytest.approx(esperado), "receita diverge da soma crua"
    assert prod["unidades"].sum() == 6

    por_item = prod.set_index("item_id")
    # Fallback do titulo = o proprio SKU; o item em cache mantem o titulo real.
    assert por_item.loc["MLB2", "title"] == "MLB2"
    assert por_item.loc["MLB3", "title"] == "MLB3"
    assert por_item.loc["MLB1", "title"] == "Produto em cache"
    assert prod["title"].notna().all()
    # O item sem cache e o maior, entao lidera o ranking.
    assert prod.iloc[0]["item_id"] == "MLB2"
    assert prod.iloc[0]["receita"] == pytest.approx(300.0)
    # Categoria desconhecida e explicita, nunca herdada de outro item.
    assert por_item.loc["MLB2", "category_name"] == SEM_CATEGORIA
    assert por_item.loc["MLB1", "category_name"] == "Categoria 1"


async def test_top_categorias_nao_joga_item_sem_cache_numa_categoria_real(pg_pool, test_seller):
    """O item sem cache nao tem categoria conhecida. Joga-lo em qualquer
    categoria real corromperia o breakdown (mesma classe de erro do bug).
    Descarta-lo tambem: a soma das categorias deixaria de bater com a receita.
    A saida certa e um balde proprio, sem category_id, e com o total fechando.
    """
    _, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto A", "CAT1", "Categoria 1")
    await _item(pg_pool, sid, "MLB2", "Produto B", "CAT2", "Categoria 2")
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 1000.0, 0.0, 0.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 2, 50.0)  # 100 -> Categoria 1
    await _order_item(pg_pool, sid, 1, "MLB2", 1, 200.0)  # 200 -> Categoria 2
    await _order_item(pg_pool, sid, 1, "MLB404", 3, 100.0)  # 300 -> sem cache

    res = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-26", n=100)
    cat = res["categorias"]

    esperado = await _receita_bruta_dos_itens(pg_pool, sid, "2026-07-25", "2026-07-26")
    assert esperado == pytest.approx(600.0)
    assert cat["receita"].sum() == pytest.approx(esperado), "categorias nao fecham com o total"
    assert cat["unidades"].sum() == 6

    # As categorias reais ficam intactas (nao absorvem a receita do item sem cache).
    reais = cat[cat["category_id"].notna()].set_index("category_id")
    assert reais.loc["CAT1", "receita"] == pytest.approx(100.0)
    assert reais.loc["CAT2", "receita"] == pytest.approx(200.0)

    # E o desconhecido vira exatamente um balde, sem category_id.
    sem = cat[cat["category_id"].isna()]
    assert len(sem) == 1
    assert sem.iloc[0]["category_name"] == SEM_CATEGORIA
    assert sem.iloc[0]["receita"] == pytest.approx(300.0)
    assert sem.iloc[0]["unidades"] == 3
    assert list(cat["category_name"])[0] == SEM_CATEGORIA  # 300 e o maior


async def test_top_produtos_mantem_item_com_categoria_fora_do_cache(pg_pool, test_seller):
    """Mesmo bug pelo segundo JOIN: o item esta em items_cache, mas a
    categoria dele nao entrou em categories_cache. O titulo e conhecido e tem
    que aparecer; a categoria e que e desconhecida. Nao pode sumir."""
    _, sid = test_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO items_cache (seller_id, item_id, title, category_id, fetched_at) "
            "VALUES ($1, 'MLB1', 'Produto A', 'CAT_SEM_NOME', now())",
            sid,
        )
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 0.0, 0.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 1, 100.0)

    res = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-26")

    prod = res["produtos"]
    assert list(prod["item_id"]) == ["MLB1"]
    assert prod.iloc[0]["title"] == "Produto A"  # o titulo real e conhecido
    assert prod.iloc[0]["category_name"] == SEM_CATEGORIA
    assert prod.iloc[0]["receita"] == pytest.approx(100.0)
    cat = res["categorias"]
    assert cat["receita"].sum() == pytest.approx(100.0)
    assert cat.iloc[0]["category_id"] is None


async def test_top_produtos_sem_cache_nao_herda_titulo_nem_categoria_de_outro_seller(
    pg_pool, test_seller, outro_seller
):
    """O LEFT JOIN continua casando por seller_id: item_id e category_id do ML
    sao globais, e o outro seller ter MLB2 em cache nao pode dar titulo ou
    categoria a quem nao tem (nem multiplicar a linha)."""
    _, sid = test_seller
    _, outro = outro_seller
    await _item(pg_pool, outro, "MLB2", "Titulo do outro", "CAT9", "Categoria do outro")
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 0.0, 0.0)
    await _order_item(pg_pool, sid, 1, "MLB2", 1, 100.0)

    res = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-26")

    prod = res["produtos"]
    assert len(prod) == 1, f"fan-out ou vazamento: esperava 1 linha, veio {len(prod)}"
    assert prod.iloc[0]["title"] == "MLB2"
    assert prod.iloc[0]["category_name"] == SEM_CATEGORIA
    assert prod.iloc[0]["receita"] == pytest.approx(100.0)
    assert res["categorias"]["receita"].sum() == pytest.approx(100.0)


async def test_top_produtos_paridade_com_a_versao_sqlite(pg_pool, test_seller):
    """O porte tem que dar os MESMOS numeros que o original em SQLite.

    Cobre agregacao multi-pedido (mesmo produto em mais de um pedido, em
    dias diferentes) e o ponto de arredondamento do ROUND no SQL — a
    superficie de top_produtos que test_fluxo_paridade... nao cobre.

    O original em SQLite nao tem seller_id; comparamos so as colunas que
    o porte tambem tem em comum com ele (mesmas colunas em produtos/categorias).
    """
    from src.metrics import top_produtos as top_produtos_sqlite
    from src.storage import connect as sqlite_connect
    from src.storage import upsert_category_cache, upsert_item_cache, upsert_order

    _, sid = test_seller

    itens = [
        ("MLB1", "Produto A", "CAT1", "Categoria 1"),
        ("MLB2", "Produto B", "CAT2", "Categoria 2"),
    ]
    # MLB1 aparece em dois pedidos, em dias diferentes -> testa GROUP BY
    # agregando por item_id atraves de multiplos pedidos.
    pedidos = [
        (1, "2026-07-25T10:00:00+00:00", [("MLB1", 2, 33.33), ("MLB2", 1, 10.0)]),
        (2, "2026-07-26T12:00:00+00:00", [("MLB1", 1, 33.33)]),
    ]

    sconn = sqlite_connect(":memory:")
    try:
        for item_id, title, category_id, category_name in itens:
            upsert_category_cache(sconn, category_id, category_name)
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
        esperado = top_produtos_sqlite(sconn, "2026-07-25", "2026-07-27")
    finally:
        sconn.close()

    for item_id, title, category_id, category_name in itens:
        await _item(pg_pool, sid, item_id, title, category_id, category_name)
    for order_id, date_closed, items in pedidos:
        total = sum(q * p for _, q, p in items)
        await _order(pg_pool, sid, order_id, date_closed, total, 0.0, 0.0)
        for item_id, qty, price in items:
            await _order_item(pg_pool, sid, order_id, item_id, qty, price)
    obtido = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-27")

    pd.testing.assert_frame_equal(
        esperado["produtos"].reset_index(drop=True),
        obtido["produtos"].reset_index(drop=True),
        check_dtype=False,
        atol=1e-6,
    )
    pd.testing.assert_frame_equal(
        esperado["categorias"].reset_index(drop=True),
        obtido["categorias"].reset_index(drop=True),
        check_dtype=False,
        atol=1e-6,
    )


async def test_top_produtos_respeita_bordas_da_janela_em_utc(pg_pool, test_seller):
    """date_to e EXCLUSIVO e o corte e em UTC — produtos E categorias tem
    que concordar (uma query com `<=` no lugar de `<` faria as duas
    divergirem entre si sem levantar excecao)."""
    _, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto A", "CAT1", "Categoria 1")

    casos = [
        (1, "2026-07-24T23:59:00+00:00", 10.0),  # fora (antes)
        (2, "2026-07-25T00:00:00+00:00", 20.0),  # dentro
        (3, "2026-07-25T23:59:00+00:00", 30.0),  # dentro
        (4, "2026-07-26T00:00:00+00:00", 40.0),  # fora (depois)
    ]
    for order_id, date_closed, preco in casos:
        await _order(pg_pool, sid, order_id, date_closed, preco, 0.0, 0.0)
        await _order_item(pg_pool, sid, order_id, "MLB1", 1, preco)

    res = await top_produtos(pg_pool, sid, "2026-07-25", "2026-07-26")

    prod = res["produtos"]
    assert len(prod) == 1
    assert prod.iloc[0]["receita"] == pytest.approx(50.0)
    assert prod.iloc[0]["unidades"] == 2

    cat = res["categorias"]
    assert len(cat) == 1
    assert cat.iloc[0]["receita"] == pytest.approx(50.0)
    assert cat.iloc[0]["unidades"] == 2


async def test_fluxo_independe_do_fuso_da_sessao(pg_pool, pg_pool_fuso_nao_utc, test_seller):
    """A agregacao por dia nao pode mudar com o TimeZone da sessao.

    Protege o `AT TIME ZONE 'UTC'` do to_char. Sem ele, um pedido as 02:00Z
    cai no dia anterior quando a sessao esta em America/Sao_Paulo (UTC-3) —
    receita diaria errada, sem erro nenhum. O pool padrao dos testes fixa
    UTC, entao so um pool nao-UTC expoe a regressao.
    """
    _, sid = test_seller
    # 02:00Z = 23:00 do dia ANTERIOR em Sao_Paulo. E o caso critico.
    await _order(pg_pool, sid, 1, "2026-07-25T02:00:00+00:00", 100.0, 10.0, 5.0)

    em_utc = await fluxo_financeiro(pg_pool, sid, "2026-07-25", "2026-07-26")
    em_sp = await fluxo_financeiro(pg_pool_fuso_nao_utc, sid, "2026-07-25", "2026-07-26")

    pd.testing.assert_frame_equal(em_utc, em_sp, check_dtype=False, atol=1e-6)
    assert em_utc.iloc[0]["date"] == "2026-07-25"

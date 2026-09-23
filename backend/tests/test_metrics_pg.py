from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest

from backend.analytics.metrics_pg import fluxo_financeiro, top_produtos

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3::timestamptz, $4, $5, $6, $7, $8, '{}'::jsonb, now())
"""


async def _order(pool, seller_id, order_id, date_closed, total, fee, ship,
                 status="paid", buyer_id=1001):
    # asyncpg 0.31 exige datetime real (nao str) para um parametro usado com
    # cast ::timestamptz no SQL -- o protocolo binario nao faz esse parse.
    dt = datetime.fromisoformat(date_closed)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    async with pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, order_id, seller_id, dt, status,
                           total, fee, ship, buyer_id)


async def _item(pool, seller_id, item_id, title, category_id, category_name):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO categories_cache (seller_id, category_id, name, fetched_at) "
            "VALUES ($1,$2,$3,now()) ON CONFLICT DO NOTHING",
            seller_id, category_id, category_name)
        await conn.execute(
            "INSERT INTO items_cache (seller_id, item_id, title, category_id, fetched_at) "
            "VALUES ($1,$2,$3,$4,now()) ON CONFLICT DO NOTHING",
            seller_id, item_id, title, category_id)


async def _order_item(pool, seller_id, order_id, item_id, qty, unit_price):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO order_items (seller_id, order_id, item_id, quantity, unit_price) "
            "VALUES ($1,$2,$3,$4,$5)",
            seller_id, order_id, item_id, qty, unit_price)


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
    assert r["custo_estimado"] == pytest.approx(150.0 * 0.55, abs=0.01)
    assert r["liquido"] == pytest.approx(150.0 - 15.0 - 7.5 - 82.5, abs=0.01)


async def test_fluxo_ignora_nao_pagos(pg_pool, test_seller):
    _, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 10.0, 5.0)
    await _order(pg_pool, sid, 2, "2026-07-25T11:00:00+00:00", 999.0, 0.0, 0.0,
                 status="cancelled")
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


async def test_fluxo_vazio_tem_as_colunas_certas(pg_pool, test_seller):
    _, sid = test_seller
    df = await fluxo_financeiro(pg_pool, sid, "2026-01-01", "2026-01-02")
    assert df.empty
    assert list(df.columns) == [
        "date", "receita_bruta", "taxas_ml", "frete", "custo_estimado", "liquido"
    ]


async def test_fluxo_colunas_numericas_sao_float(pg_pool, test_seller):
    """numeric do Postgres volta como Decimal no asyncpg — tem que virar float."""
    _, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 10.0, 5.0)
    df = await fluxo_financeiro(pg_pool, sid, "2026-07-25", "2026-07-26")
    for col in ["receita_bruta", "taxas_ml", "frete", "custo_estimado", "liquido"]:
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
            upsert_order(sconn, {
                "order_id": oid, "date_closed": dt, "status": "paid",
                "total_amount": total, "marketplace_fee": fee, "shipping_cost": ship,
                "buyer_id": 1001, "raw_json": "{}", "items": [],
            })
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
        atol=0.01,
    )


# ---------- top_produtos ----------

async def test_top_produtos_ranqueia_por_receita(pg_pool, test_seller):
    _, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto A", "CAT1", "Categoria 1")
    await _item(pg_pool, sid, "MLB2", "Produto B", "CAT1", "Categoria 1")
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 300.0, 0.0, 0.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 2, 50.0)    # 100
    await _order_item(pg_pool, sid, 1, "MLB2", 1, 200.0)   # 200

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
        "item_id", "title", "category_name", "unidades", "receita"
    ]
    assert list(res["categorias"].columns) == [
        "category_id", "category_name", "unidades", "receita"
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

"""Custo de produto informado pelo vendedor — comportamento de vigência.

O que estes testes protegem é uma afirmação do produto: a margem é
*calculada*, não estimada. Isso só é verdade se o custo informado hoje não
contaminar o passado — ver `backend/migrations/0008_custo_de_produto.sql`.

Os horários são 13:00 UTC (10:00 em Brasília) de propósito: longe da
meia-noite nos dois fusos, para que um teste de vigência não falhe por um
motivo de fuso e mascare o que está medindo. A divergência de fuso tem teste
próprio em `test_metrics_pg.py`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from backend.analytics.metrics_pg import fluxo_financeiro

pytestmark = pytest.mark.asyncio

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3::timestamptz, 'paid', $4, 0, 0, 1001, '{}'::jsonb, now())
"""


async def _pedido(pool, seller_id, order_id, quando, itens):
    """Grava um pedido pago e seus itens. `itens` = [(item_id, qtd, preco)]."""
    dt = datetime.fromisoformat(quando)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    total = sum(q * p for _, q, p in itens)
    async with pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, order_id, seller_id, dt, total)
        for item_id, qtd, preco in itens:
            await conn.execute(
                "INSERT INTO order_items (seller_id, order_id, item_id, quantity, unit_price)"
                " VALUES ($1,$2,$3,$4,$5)",
                seller_id,
                order_id,
                item_id,
                qtd,
                preco,
            )


async def _custo(pool, seller_id, item_id, desde, valor):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO product_costs (seller_id, item_id, vigente_desde, custo_unitario)"
            " VALUES ($1,$2,$3,$4)"
            " ON CONFLICT (seller_id, item_id, vigente_desde)"
            " DO UPDATE SET custo_unitario = excluded.custo_unitario",
            seller_id,
            item_id,
            date.fromisoformat(desde),
            valor,
        )


async def test_pedido_antes_da_primeira_vigencia_fica_sem_custo(pg_pool, test_seller):
    """O custo informado hoje NÃO reescreve a margem de ontem.

    É o teste central da feature. Sem ele, corrigir um custo em outubro muda
    o resultado de setembro — um mês já fechado vira outro número, em
    silêncio, num produto cujo argumento é "calculada, não estimada".
    """
    _, sid = test_seller
    await _pedido(pg_pool, sid, 1, "2026-07-15T13:00:00+00:00", [("MLB1", 2, 50.0)])
    await _pedido(pg_pool, sid, 2, "2026-07-25T13:00:00+00:00", [("MLB1", 2, 50.0)])
    await _custo(pg_pool, sid, "MLB1", "2026-07-20", 10.0)

    df = await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")
    por_dia = df.set_index("date")

    antes = por_dia.loc["2026-07-15"]
    assert antes["custo_produtos"] == 0, "pedido anterior à vigência não pode herdar o custo"
    assert antes["receita_sem_custo"] == 100.0, "e a receita dele conta como não coberta"
    assert antes["margem_contribuicao"] == 100.0

    depois = por_dia.loc["2026-07-25"]
    assert depois["custo_produtos"] == 20.0, "2 unidades a 10,00"
    assert depois["receita_sem_custo"] == 0.0
    assert depois["margem_contribuicao"] == 80.0


async def test_cada_pedido_usa_a_vigencia_que_valia_no_dia_dele(pg_pool, test_seller):
    """Com duas vigências, cada pedido pega a sua — a última anterior a ele.

    Este é o teste a quebrar por mutação: trocar
    `ORDER BY c.vigente_desde DESC LIMIT 1` por um custo único faz os três
    dias usarem o mesmo valor.
    """
    _, sid = test_seller
    await _custo(pg_pool, sid, "MLB1", "2026-07-01", 10.0)
    await _custo(pg_pool, sid, "MLB1", "2026-07-20", 15.0)

    await _pedido(pg_pool, sid, 1, "2026-07-10T13:00:00+00:00", [("MLB1", 1, 100.0)])
    await _pedido(pg_pool, sid, 2, "2026-07-20T13:00:00+00:00", [("MLB1", 1, 100.0)])
    await _pedido(pg_pool, sid, 3, "2026-07-25T13:00:00+00:00", [("MLB1", 1, 100.0)])

    por_dia = (await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")).set_index("date")

    assert por_dia.loc["2026-07-10", "custo_produtos"] == 10.0
    # No PRÓPRIO dia da virada o custo novo já vale: `vigente_desde <= data`.
    assert por_dia.loc["2026-07-20", "custo_produtos"] == 15.0
    assert por_dia.loc["2026-07-25", "custo_produtos"] == 15.0


async def test_receita_sem_custo_mede_so_os_itens_sem_custo(pg_pool, test_seller):
    """A coluna que torna a margem honesta.

    Sem ela, um vendedor com 1 de 2 produtos preenchidos veria a margem quase
    intacta. Mutação: zerar `receita_sem_custo` e este teste cai.
    """
    _, sid = test_seller
    await _pedido(
        pg_pool,
        sid,
        1,
        "2026-07-25T13:00:00+00:00",
        [("COM_CUSTO", 1, 300.0), ("SEM_CUSTO", 1, 700.0)],
    )
    await _custo(pg_pool, sid, "COM_CUSTO", "2026-07-01", 120.0)

    linha = (await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")).iloc[0]

    assert linha["receita_bruta"] == 1000.0
    assert linha["custo_produtos"] == 120.0
    assert linha["receita_sem_custo"] == 700.0, "só o item sem custo informado"
    assert linha["margem_contribuicao"] == 880.0


async def test_custo_zero_conta_como_informado(pg_pool, test_seller):
    """Zero é uma afirmação; ausência não é.

    "Este produto não me custa nada" é informação, e tem que sair de
    `receita_sem_custo`. Se zero fosse tratado como vazio, o vendedor que
    preencheu tudo veria cobertura abaixo de 100%.
    """
    _, sid = test_seller
    await _pedido(pg_pool, sid, 1, "2026-07-25T13:00:00+00:00", [("BRINDE", 3, 40.0)])
    await _custo(pg_pool, sid, "BRINDE", "2026-07-01", 0.0)

    linha = (await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")).iloc[0]

    assert linha["custo_produtos"] == 0.0
    assert linha["receita_sem_custo"] == 0.0, "custo zero é informado, não ausente"
    assert linha["margem_contribuicao"] == 120.0


async def test_custo_de_outro_vendedor_nao_vaza(pg_pool, test_seller, outro_seller):
    """Mesmo `item_id` em dois vendedores: o custo de um não desconta do outro.

    O `item_id` do Mercado Livre é único globalmente, mas nada no schema
    impede dois sellers de terem o mesmo — e o JOIN do custo precisa casar
    `seller_id` também, não só `item_id`.
    """
    _, sid = test_seller
    _, outro_sid = outro_seller

    await _pedido(pg_pool, sid, 1, "2026-07-25T13:00:00+00:00", [("MLB1", 1, 100.0)])
    await _custo(pg_pool, outro_sid, "MLB1", "2026-07-01", 90.0)

    linha = (await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")).iloc[0]

    assert linha["custo_produtos"] == 0.0, "custo do vizinho não pode descontar aqui"
    assert linha["receita_sem_custo"] == 100.0

"""Minimização dos dados de pagamento (docs/specs/2026-10-28-minimizacao-pagamentos-design.md).

O que estes testes guardam são as duas metades da decisão:
- os identificadores do meio de pagamento do comprador NÃO chegam ao banco,
  nem pela ingestão nem pelo que já estava guardado (migration 0014);
- os VALORES do pagamento continuam, porque é com eles que se audita número
  (o reembolso parcial do item 4b foi medido assim).
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.ml.ingest_pg import CAMPOS_DE_PAGAMENTO_DESCARTADOS

from .test_ingest_pg import ClienteFake, _ingere, _pedido

IDENTIFICADORES = {
    "card_id": 123456789,
    "authorization_code": "A1B2C3",
    "payer_id": 555,
    "issuer_id": "25",
    "activation_uri": "https://exemplo/ativar",
    "atm_transfer_reference": {"transaction_id": "XYZ"},
}
VALORES = {
    "transaction_amount": 117.0,
    "transaction_amount_refunded": 78.0,
    "total_paid_amount": 117.0,
    "installments": 3,
    "status": "approved",
}

MIGRATION = Path(__file__).resolve().parent.parent / "migrations" / "0014_minimiza_pagamentos.sql"


def _pedido_com_pagamento(order_id: int) -> dict:
    pedido = _pedido(order_id)
    pedido["payments"] = [{**VALORES, **IDENTIFICADORES}]
    return pedido


async def _pagamento_gravado(pool, sid, order_id) -> dict:
    async with pool.acquire() as conn:
        bruto = await conn.fetchval(
            "SELECT raw_json FROM orders WHERE seller_id=$1 AND order_id=$2", sid, order_id
        )
    bruto = bruto if isinstance(bruto, dict) else json.loads(bruto)
    return bruto["payments"][0]


def test_a_lista_cobre_exatamente_os_identificadores_da_spec():
    assert set(CAMPOS_DE_PAGAMENTO_DESCARTADOS) == set(IDENTIFICADORES)


async def test_ingestao_nao_grava_identificador_de_pagamento(pg_pool, test_seller):
    _, sid = test_seller
    items = {"MLB1": {"title": "Produto", "category_id": "CAT1"}}

    await _ingere(pg_pool, sid, ClienteFake(paid=[_pedido_com_pagamento(1)], items=items))

    pagamento = await _pagamento_gravado(pg_pool, sid, 1)
    assert set(pagamento) & set(IDENTIFICADORES) == set()


async def test_ingestao_mantem_os_valores_do_pagamento(pg_pool, test_seller):
    """Os valores são o que permite auditar: não podem sair junto."""
    _, sid = test_seller
    items = {"MLB1": {"title": "Produto", "category_id": "CAT1"}}

    await _ingere(pg_pool, sid, ClienteFake(paid=[_pedido_com_pagamento(1)], items=items))

    assert await _pagamento_gravado(pg_pool, sid, 1) == VALORES


async def test_migration_limpa_o_que_ja_estava_guardado(pg_pool, test_seller, outro_seller):
    """Pedido gravado antes da minimização: sai o identificador, ficam os
    valores, e pedido sem pagamento passa intacto."""
    _, sid = test_seller
    _, outro = outro_seller
    async with pg_pool.acquire() as conn:
        for vendedor, order_id, bruto in (
            (sid, 1, _pedido_com_pagamento(1)),
            (outro, 2, _pedido_com_pagamento(2)),
            (sid, 3, {**_pedido(3), "payments": []}),
        ):
            await conn.execute(
                "INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,"
                " marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)"
                " VALUES ($1, $2, now(), 'paid', 117, 0, 0, 555, $3::jsonb, now())",
                order_id,
                vendedor,
                json.dumps(bruto),
            )
        await conn.execute(MIGRATION.read_text(encoding="utf-8"))

    assert await _pagamento_gravado(pg_pool, sid, 1) == VALORES
    assert await _pagamento_gravado(pg_pool, outro, 2) == VALORES
    async with pg_pool.acquire() as conn:
        vazio = await conn.fetchval(
            "SELECT raw_json->'payments' FROM orders WHERE seller_id=$1 AND order_id=3", sid
        )
    assert json.loads(vazio) == []

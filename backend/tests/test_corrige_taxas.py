"""Testes do backfill de taxa/frete a partir do raw_json."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from backend.scripts.corrige_taxas_do_raw_json import corrige_taxas
from backend.tests.test_ingest_pg import _pedido


async def _insere_legado(pg_pool, seller_id, pedido, *, taxa=0, frete=0):
    """Linha como a ingestao antiga deixava: taxa/frete zerados, raw_json completo."""
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount, "
            "marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, 555, $8::jsonb, now())",
            pedido["id"],
            seller_id,
            datetime(2026, 7, 15, tzinfo=UTC),
            pedido["status"],
            pedido["total_amount"],
            taxa,
            frete,
            json.dumps(pedido),
        )


async def _valores(pg_pool, seller_id, order_id):
    async with pg_pool.acquire() as conn:
        linha = await conn.fetchrow(
            "SELECT marketplace_fee, shipping_cost FROM orders "
            "WHERE seller_id = $1 AND order_id = $2",
            seller_id,
            order_id,
        )
    return linha["marketplace_fee"], linha["shipping_cost"]


async def test_dry_run_relata_mas_nao_grava(pg_pool, test_seller):
    _u, seller_id = test_seller
    await _insere_legado(
        pg_pool, seller_id, _pedido(1, sale_fee=6.0, quantity=2, shipping_cost=3.0)
    )

    resumo = await corrige_taxas(pg_pool, aplicar=False)

    assert resumo.a_mudar == 1
    assert resumo.taxa_antes == Decimal("0")
    assert resumo.taxa_depois == Decimal("12.00")
    assert await _valores(pg_pool, seller_id, 1) == (Decimal("0"), Decimal("0")), "dry-run gravou"


async def test_apply_corrige_e_e_seguro_rodar_duas_vezes(pg_pool, test_seller):
    _u, seller_id = test_seller
    await _insere_legado(
        pg_pool, seller_id, _pedido(1, sale_fee=6.0, quantity=2, shipping_cost=3.0)
    )
    await _insere_legado(pg_pool, seller_id, _pedido(2, sale_fee=4.32, quantity=1))

    primeira = await corrige_taxas(pg_pool, aplicar=True)
    assert primeira.a_mudar == 2
    assert await _valores(pg_pool, seller_id, 1) == (Decimal("12.00"), Decimal("3.00"))
    assert await _valores(pg_pool, seller_id, 2) == (Decimal("4.32"), Decimal("0"))

    segunda = await corrige_taxas(pg_pool, aplicar=True)
    assert segunda.a_mudar == 0
    assert segunda.inalterados == 2
    assert segunda.taxa_antes == segunda.taxa_depois == Decimal("16.32")
    assert await _valores(pg_pool, seller_id, 1) == (Decimal("12.00"), Decimal("3.00"))


async def test_seller_de_demo_nao_e_tocado(pg_pool, test_seller):
    """O seed grava taxa direto na coluna e deixa um raw_json sintetico sem sale_fee.

    Recalcular a partir dele apagaria taxas corretas do demo.
    """
    _u, seller_id = test_seller
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET is_demo = true WHERE id = $1", seller_id)
    sintetico = _pedido(1)
    del sintetico["order_items"][0]["sale_fee"]
    await _insere_legado(pg_pool, seller_id, sintetico, taxa=44)

    resumo = await corrige_taxas(pg_pool, aplicar=True)

    # >= 1: o banco de teste local pode guardar sobras de outros sellers de demo.
    assert resumo.demo_ignorados >= 1 and resumo.examinados == 0
    assert (await _valores(pg_pool, seller_id, 1))[0] == Decimal("44")


async def test_pedido_sem_sale_fee_no_raw_json_e_pulado_nao_zerado(pg_pool, test_seller):
    _u, seller_id = test_seller
    sem_taxa = _pedido(1)
    del sem_taxa["order_items"][0]["sale_fee"]
    await _insere_legado(pg_pool, seller_id, sem_taxa, taxa=7)

    resumo = await corrige_taxas(pg_pool, aplicar=True)

    assert resumo.sem_sale_fee == 1 and resumo.a_mudar == 0
    assert (await _valores(pg_pool, seller_id, 1))[0] == Decimal("7")

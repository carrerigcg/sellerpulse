# backend/ml/ingest_pg.py
"""Ingestao de uma janela de dados do Mercado Livre em Postgres.

Port de `src/ingest.py`, com duas diferencas estruturais:

1. Grava por `(seller_id, order_id)`. Toda linha de toda tabela leva o
   seller_id — e o unico mecanismo de isolamento entre tenants nas queries do
   backend (a RLS nao se aplica ao papel `postgres`).
2. Ingere UMA janela de datas, nao os 6 meses. Quem fatia o periodo em meses e
   grava o progresso e o worker; aqui fica so o trabalho de ingerir, o que
   torna esta funcao testavel sem fila.

O `MLClient` continua sincrono (`requests`). Como o worker compartilha
processo com a API, TODA chamada HTTP passa por `asyncio.to_thread` — chamar
direto congelaria a API durante a ingestao.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import asyncpg

_UPSERT_ORDER = """
    INSERT INTO orders (
        order_id, seller_id, date_closed, status, total_amount,
        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, now())
    ON CONFLICT (seller_id, order_id) DO UPDATE SET
        date_closed     = excluded.date_closed,
        status          = excluded.status,
        total_amount    = excluded.total_amount,
        marketplace_fee = excluded.marketplace_fee,
        shipping_cost   = excluded.shipping_cost,
        buyer_id        = excluded.buyer_id,
        raw_json        = excluded.raw_json,
        fetched_at      = excluded.fetched_at
"""

_UPSERT_CLAIM = """
    INSERT INTO claims (seller_id, claim_id, order_id, status, date_created, raw_json, fetched_at)
    VALUES ($1, $2, $3, $4, $5, $6::jsonb, now())
    ON CONFLICT (seller_id, claim_id) DO UPDATE SET
        order_id     = excluded.order_id,
        status       = excluded.status,
        date_created = excluded.date_created,
        raw_json     = excluded.raw_json,
        fetched_at   = excluded.fetched_at
"""


@dataclass
class ResultadoIngestao:
    total_orders: int = 0
    distinct_items: int = 0
    distinct_buyers: int = 0
    total_claims: int = 0
    warnings: list[str] = field(default_factory=list)


def _para_datetime(valor: str) -> datetime:
    """ISO 8601 do ML -> datetime aware em UTC.

    O ML devolve com offset ('...-03:00'). Sem tz-aware, o Postgres assumiria
    o fuso da sessao e o pedido cairia no dia errado no agrupamento diario —
    o mesmo bug que a Sprint 1 fechou nas queries analiticas.
    """
    dt = datetime.fromisoformat(valor)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


async def ingest_janela(
    pool: asyncpg.Pool,
    seller_id: uuid.UUID,
    *,
    client,
    ml_seller_id: int,
    date_from: datetime,
    date_to: datetime,
    campo_data: str = "date_created",
    incluir_claims: bool = False,
    on_progress=None,
) -> ResultadoIngestao:
    """Ingere [date_from, date_to) do vendedor. Idempotente."""
    resultado = ResultadoIngestao()
    de, ate = date_from.isoformat(), date_to.isoformat()

    pedidos: list[dict] = []
    for status in ("paid", "cancelled"):
        try:
            lote = await asyncio.to_thread(
                lambda s=status: client.get_orders(
                    seller_id=ml_seller_id,
                    status=s,
                    date_from=de,
                    date_to=ate,
                    campo_data=campo_data,
                )
            )
            pedidos.extend(lote)
        except Exception as exc:  # noqa: BLE001 — boundary de rede
            resultado.warnings.append(f"Falha na fase pedidos {status}: {exc}")

    itens_vistos: set[str] = set()
    compradores: set[int] = set()

    for indice, bruto in enumerate(pedidos, start=1):
        try:
            avisos = await _persiste_pedido(pool, seller_id, client, bruto, itens_vistos)
        except Exception as exc:  # noqa: BLE001 — boundary
            resultado.warnings.append(
                f"Falha ao persistir pedido {bruto.get('id', f'idx={indice}')}: {exc}"
            )
            continue
        resultado.warnings.extend(avisos)
        resultado.total_orders += 1
        comprador = (bruto.get("buyer") or {}).get("id")
        if comprador:
            compradores.add(int(comprador))
        if on_progress is not None:
            await on_progress("Processando pedidos", indice, len(pedidos))

    if incluir_claims:
        try:
            reclamacoes = await asyncio.to_thread(
                client.get_claims, seller_id=ml_seller_id, date_from=de, date_to=ate
            )
        except Exception as exc:  # noqa: BLE001
            resultado.warnings.append(f"Falha na fase claims: {exc}")
            reclamacoes = []
        for c in reclamacoes:
            try:
                await _persiste_claim(pool, seller_id, c)
                resultado.total_claims += 1
            except Exception as exc:  # noqa: BLE001
                resultado.warnings.append(f"Falha ao persistir claim: {exc}")

    resultado.distinct_items = len(itens_vistos)
    resultado.distinct_buyers = len(compradores)
    return resultado


async def _persiste_pedido(
    pool: asyncpg.Pool,
    seller_id: uuid.UUID,
    client,
    bruto: dict,
    itens_vistos: set[str],
) -> list[str]:
    """Normaliza e grava o pedido + itens. Devolve warnings do enriquecimento.

    Enriquecimento roda DEPOIS do commit do pedido, em loop isolado: falha de
    API num item nao pode descartar um pedido que ja esta correto no banco.
    """
    order_id = int(bruto["id"])

    pagamentos = bruto.get("payments") or []
    taxa = sum(p.get("marketplace_fee", 0.0) or 0.0 for p in pagamentos)
    frete = (bruto.get("shipping") or {}).get("list_cost", 0.0) or 0.0

    itens: list[dict] = []
    for oi in bruto.get("order_items") or []:
        item_id = (oi.get("item") or {}).get("id")
        if not item_id:
            continue
        itens.append(
            {
                "item_id": item_id,
                "quantity": oi.get("quantity", 1),
                "unit_price": oi.get("unit_price", 0.0),
            }
        )
        itens_vistos.add(item_id)

    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(
            _UPSERT_ORDER,
            order_id,
            seller_id,
            _para_datetime(bruto.get("date_closed") or bruto["date_created"]),
            bruto["status"],
            bruto.get("total_amount", 0.0),
            taxa,
            frete,
            (bruto.get("buyer") or {}).get("id"),
            json.dumps(bruto),
        )
        # DELETE + INSERT em vez de upsert item a item: se o pedido perdeu
        # um item numa revisao do ML, o upsert deixaria o antigo pra tras.
        await conn.execute(
            "DELETE FROM order_items WHERE seller_id = $1 AND order_id = $2",
            seller_id,
            order_id,
        )
        for item in itens:
            await conn.execute(
                "INSERT INTO order_items (seller_id, order_id, item_id, quantity, unit_price) "
                "VALUES ($1, $2, $3, $4, $5)",
                seller_id,
                order_id,
                item["item_id"],
                item["quantity"],
                item["unit_price"],
            )

    avisos: list[str] = []
    for item in itens:
        try:
            await _garante_cache_de_item(pool, seller_id, client, item["item_id"])
        except Exception as exc:  # noqa: BLE001 — boundary
            avisos.append(f"Falha ao enriquecer item {item['item_id']} do pedido {order_id}: {exc}")
    return avisos


async def _garante_cache_de_item(
    pool: asyncpg.Pool, seller_id: uuid.UUID, client, item_id: str
) -> None:
    """Preenche items_cache/categories_cache do SELLER, se faltar.

    O cache e por seller de proposito: reaproveitar o de outro tenant faria o
    dashboard de um mostrar titulo de produto que ele nao vende.
    """
    async with pool.acquire() as conn:
        existe = await conn.fetchval(
            "SELECT 1 FROM items_cache WHERE seller_id = $1 AND item_id = $2", seller_id, item_id
        )
    if existe:
        return

    item = await asyncio.to_thread(client.get_item, item_id)
    titulo = item.get("title", "")
    category_id = item.get("category_id", "")

    if category_id:
        async with pool.acquire() as conn:
            tem_categoria = await conn.fetchval(
                "SELECT 1 FROM categories_cache WHERE seller_id = $1 AND category_id = $2",
                seller_id,
                category_id,
            )
        if not tem_categoria:
            categoria = await asyncio.to_thread(client.get_category, category_id)
            async with pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO categories_cache (seller_id, category_id, name, fetched_at) "
                    "VALUES ($1, $2, $3, now()) ON CONFLICT DO NOTHING",
                    seller_id,
                    category_id,
                    categoria.get("name", ""),
                )

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO items_cache (seller_id, item_id, title, category_id, fetched_at) "
            "VALUES ($1, $2, $3, $4, now()) "
            "ON CONFLICT (seller_id, item_id) DO UPDATE SET "
            "title = excluded.title, category_id = excluded.category_id, "
            "fetched_at = excluded.fetched_at",
            seller_id,
            item_id,
            titulo,
            category_id,
        )


async def _persiste_claim(pool: asyncpg.Pool, seller_id: uuid.UUID, claim: dict) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            _UPSERT_CLAIM,
            seller_id,
            int(claim.get("id") or claim["claim_id"]),
            int(claim["resource_id"]) if claim.get("resource_id") else claim.get("order_id"),
            claim.get("status", "unknown"),
            _para_datetime(claim["date_created"]),
            json.dumps(claim),
        )

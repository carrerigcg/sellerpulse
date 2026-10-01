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


def tem_sale_fee(bruto: dict) -> bool:
    """O pedido traz `sale_fee` em pelo menos um item?"""
    return any(oi.get("sale_fee") is not None for oi in bruto.get("order_items") or [])


def extrai_taxa_e_frete(bruto: dict) -> tuple[float, float]:
    """(taxa do Mercado Livre, frete) de um pedido no formato REAL da API.

    NAO "simplifique" isto de volta para `payments[].marketplace_fee` e
    `shipping.list_cost`. Esses campos nao foram renomeados: NUNCA existiram nos
    payloads reais do ML. O codigo os lia mesmo assim, o `.get(..., 0.0)` engolia
    a ausencia e toda taxa e todo frete eram gravados como zero — R$ 16 mil de
    taxa some da margem sem nenhum erro (achado na primeira ingestao real).

    Onde o dado realmente esta (conferido em `raw_json` de pedidos de producao):

    - taxa: `order_items[].sale_fee`, POR UNIDADE. Dois itens de R$ 36 chegaram
      com sale_fee 4.32 (12% de 36, nao de 72), entao a taxa da linha e
      `sale_fee * quantity`. `payments[]` traz transaction_amount, taxes_amount,
      shipping_cost, total_paid_amount — nenhum deles e a comissao.
    - frete: `shipping_cost` na RAIZ do pedido (costuma vir `null`). `shipping`
      e so `{"id": ...}`. Atencao: `payments[].shipping_cost` e o frete que o
      COMPRADOR pagou (soma no total_paid_amount), nao custo do vendedor.

    Sem fallback pros nomes antigos, de proposito: um fallback pra campo que
    nunca vem e exatamente o que escondeu o erro por meses. Ausencia vira 0.0 —
    o aviso de `ingest_janela` cobre o caso de a ausencia ser sistematica.
    Fica publica pra que o script de backfill reuse a mesma regra, sem copia.
    """
    taxa = sum(
        (oi.get("sale_fee") or 0.0) * (oi.get("quantity") or 1)
        for oi in bruto.get("order_items") or []
    )
    frete = bruto.get("shipping_cost") or 0.0
    return round(taxa, 2), round(frete, 2)


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
    """Ingere [date_from, date_to) do vendedor. Idempotente.

    Falhas de rede em `get_orders` PROPAGAM (abortam a janela inteira) — ver
    o comentário no loop abaixo. Falhas em enriquecimento de item/categoria e
    na fase de claims só geram warning e a ingestão segue: aquelas degradam
    um rótulo no dashboard, não corrompem receita.
    """
    resultado = ResultadoIngestao()
    de, ate = date_from.isoformat(), date_to.isoformat()

    pedidos: list[dict] = []
    for status in ("paid", "cancelled"):
        # SEM try/except aqui, de proposito. Engolir a falha num warning daria a
        # janela por concluida faltando pedidos — e se o que falhou foi a busca
        # de cancelados, a receita fica inflada. Pior: o delta seguinte filtra
        # por date_last_updated numa janela nova e nunca volta pra buscar esses
        # pedidos, entao o numero fica errado PRA SEMPRE, sem erro nenhum.
        # Estourando, a fila repesca o job e tenta de novo (o upsert e
        # idempotente, entao reprocessar nao duplica nada).
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

    itens_vistos: set[str] = set()
    compradores: set[int] = set()
    pedidos_sem_sale_fee = 0

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
        if not tem_sale_fee(bruto):
            pedidos_sem_sale_fee += 1
        comprador = (bruto.get("buyer") or {}).get("id")
        if comprador:
            compradores.add(int(comprador))
        if on_progress is not None:
            await on_progress("Processando pedidos", indice, len(pedidos))

    # Um aviso por janela, so quando NENHUM pedido traz sale_fee. Pedido isolado
    # sem ele existe e, avisado um a um, viraria ruido em milhares de pedidos;
    # ausencia total e a assinatura de o ML ter mudado o payload — o mesmo modo de
    # falha silencioso que zerou as taxas por meses.
    if resultado.total_orders and pedidos_sem_sale_fee == resultado.total_orders:
        resultado.warnings.append(
            f"Nenhum dos {resultado.total_orders} pedidos da janela trouxe "
            "order_items[].sale_fee; a taxa do ML foi gravada como 0. "
            "O formato do payload pode ter mudado."
        )

    if incluir_claims:
        # O endpoint de claims esta BLOQUEADO pra esta aplicacao. Verificado em
        # 2026-10-01 contra a conta real, com os argumentos corretos:
        #
        #   403 {"code":"PA_UNAUTHORIZED_RESULT_FROM_POLICIES",
        #        "message":"At least one policy returned UNAUTHORIZED.",
        #        "blocked_by":"PolicyAgent"}
        #
        # Nao e bug nosso e nao e token expirado: e politica de nivel de
        # aplicacao no DevCenter do ML. Registrado aqui pra ninguem gastar uma
        # tarde depurando de novo — se um dia a permissao for liberada, a fase
        # volta a popular `claims` sozinha, sem mudanca de codigo.
        #
        # Consequencia hoje: `claims` fica vazia e `reputacao_devolucao`
        # reporta zero reclamacoes. Nenhuma tela da web usa claims, entao o
        # impacto e so no relatorio em PDF (camada legada). O warning por
        # janela ja deixa isso visivel na tela de conexao.
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

    taxa, frete = extrai_taxa_e_frete(bruto)

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


def _order_id_do_claim(claim: dict) -> int | None:
    """resource_id, senao order_id, senao None.

    Checa `is not None` e nao truthiness: o ML manda id como numero JSON, e o
    inteiro 0 e falsy — com `if claim.get(...)` um resource_id legitimo de 0
    seria descartado em silencio. `claims.order_id` e nulavel, entao claim sem
    pedido associado e representavel e nao e erro.
    """
    bruto = claim.get("resource_id")
    if bruto is None:
        bruto = claim.get("order_id")
    return int(bruto) if bruto is not None else None


async def _persiste_claim(pool: asyncpg.Pool, seller_id: uuid.UUID, claim: dict) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            _UPSERT_CLAIM,
            seller_id,
            int(claim.get("id") or claim["claim_id"]),
            _order_id_do_claim(claim),
            claim.get("status", "unknown"),
            _para_datetime(claim["date_created"]),
            json.dumps(claim),
        )

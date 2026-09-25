# backend/seed.py
"""Popula um seller Postgres com dados sinteticos, reaproveitando `src/demo_data.py`.

Sem isso, um seller novo (inclusive apos o OAuth real da Sprint 2) abre com
todas as tabelas vazias -- nada pra mostrar no dashboard. `seed_postgres` gera
catalogo + pedidos + claims deterministicos (mesmas funcoes puras usadas pelo
`data/demo.db` do SQLite) e grava no schema multi-tenant, isolado por
`seller_id`.

Idempotente: cada INSERT usa `ON CONFLICT DO NOTHING` na chave composta da
tabela, entao rodar duas vezes pro mesmo seller nao duplica nada -- a segunda
chamada devolve contagens zeradas.

Tudo roda dentro de uma unica transacao: ou o seller fica totalmente semeado,
ou (em caso de erro) nada e gravado.
"""

from __future__ import annotations

from typing import Any

from backend.analytics._common import _parse_boundary
from src.demo_data import DEFAULT_SEED, generate_catalog, generate_claims, generate_orders

_TABELAS = ("categories", "items", "orders", "order_items", "claims")

_TABELA_SQL = {
    "categories": "categories_cache",
    "items": "items_cache",
    "orders": "orders",
    "order_items": "order_items",
    "claims": "claims",
}

_INSERT_CATEGORY = """
    INSERT INTO categories_cache (seller_id, category_id, name, fetched_at)
    VALUES ($1, $2, $3, now())
    ON CONFLICT DO NOTHING
"""

_INSERT_ITEM = """
    INSERT INTO items_cache (seller_id, item_id, title, category_id, fetched_at)
    VALUES ($1, $2, $3, $4, now())
    ON CONFLICT DO NOTHING
"""

_INSERT_ORDER = """
    INSERT INTO orders (
        order_id, seller_id, date_closed, status, total_amount,
        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, now())
    ON CONFLICT DO NOTHING
"""

_INSERT_ORDER_ITEM = """
    INSERT INTO order_items (seller_id, order_id, item_id, quantity, unit_price)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT DO NOTHING
"""

_INSERT_CLAIM = """
    INSERT INTO claims (seller_id, claim_id, order_id, status, date_created, raw_json, fetched_at)
    VALUES ($1, $2, $3, $4, $5, $6::jsonb, now())
    ON CONFLICT DO NOTHING
"""


def _dedupe_order_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Soma quantidades de item_id repetido dentro do mesmo pedido.

    `generate_orders` usa `rng.choices` com reposicao -- o mesmo item_id pode
    aparecer mais de uma vez no mesmo pedido. A PK de `order_items` e
    (seller_id, order_id, item_id), entao inserir as linhas cruas violaria a
    chave. Mesma logica de `generate_demo_db` em `src/demo_data.py`.
    """
    vistos: dict[str, dict[str, Any]] = {}
    for item in items:
        if item["item_id"] in vistos:
            vistos[item["item_id"]]["quantity"] += item["quantity"]
        else:
            vistos[item["item_id"]] = dict(item)
    return list(vistos.values())


async def _contagens(conn, seller_id) -> dict[str, int]:
    return {
        chave: await conn.fetchval(
            f"SELECT count(*) FROM {tabela_sql} WHERE seller_id = $1", seller_id
        )
        for chave, tabela_sql in _TABELA_SQL.items()
    }


async def seed_postgres(
    pool,
    seller_id,
    *,
    seed: int = DEFAULT_SEED,
    n_categories: int = 10,
    n_products: int = 50,
    weeks_back: int = 12,
    claim_rate: float = 0.04,
) -> dict[str, int]:
    """Popula `seller_id` com catalogo + pedidos + claims sinteticos.

    Args:
        pool: pool asyncpg (`backend.db.get_pool()`).
        seller_id: UUID do seller a popular -- precisa ja existir em `sellers`.
        seed: semente do gerador determinístico (default `DEFAULT_SEED` de
            `src/demo_data.py`, a mesma usada pelo `data/demo.db`).
        n_categories, n_products, weeks_back, claim_rate: repassados direto
            pra `generate_catalog` / `generate_orders` / `generate_claims`.

    Returns:
        dict com as contagens de linhas efetivamente INSERIDAS nesta chamada
        (chaves: categories, items, orders, order_items, claims). Numa
        segunda chamada com os mesmos parametros, todas as contagens vem 0 —
        o `ON CONFLICT DO NOTHING` torna a operacao idempotente.
    """
    catalog = generate_catalog(seed=seed, n_categories=n_categories, n_products=n_products)
    orders = generate_orders(catalog=catalog, seed=seed, weeks_back=weeks_back)
    claims = generate_claims(orders=orders, seed=seed, rate=claim_rate)

    async with pool.acquire() as conn, conn.transaction():
        contagens_antes = await _contagens(conn, seller_id)

        categorias_args = [
            (seller_id, cat["category_id"], cat["name"]) for cat in catalog["categories"]
        ]
        await conn.executemany(_INSERT_CATEGORY, categorias_args)

        itens_args = [
            (seller_id, prod["item_id"], prod["title"], prod["category_id"])
            for prod in catalog["products"]
        ]
        await conn.executemany(_INSERT_ITEM, itens_args)

        pedidos_args = []
        order_items_args = []
        for order in orders:
            pedidos_args.append(
                (
                    order["order_id"],
                    seller_id,
                    _parse_boundary(order["date_closed"]),
                    order["status"],
                    order["total_amount"],
                    order["marketplace_fee"],
                    order["shipping_cost"],
                    order["buyer_id"],
                    order["raw_json"],
                )
            )
            for item in _dedupe_order_items(order["items"]):
                order_items_args.append(
                    (
                        seller_id,
                        order["order_id"],
                        item["item_id"],
                        item["quantity"],
                        item["unit_price"],
                    )
                )
        await conn.executemany(_INSERT_ORDER, pedidos_args)
        await conn.executemany(_INSERT_ORDER_ITEM, order_items_args)

        claims_args = [
            (
                seller_id,
                c["claim_id"],
                c["order_id"],
                c["status"],
                _parse_boundary(c["date_created"]),
                c["raw_json"],
            )
            for c in claims
        ]
        await conn.executemany(_INSERT_CLAIM, claims_args)

        contagens_depois = await _contagens(conn, seller_id)

    return {chave: contagens_depois[chave] - contagens_antes[chave] for chave in _TABELAS}

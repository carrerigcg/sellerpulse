"""Gerador de dados sintéticos determinístico para o SellerPulse.

Gera `data/demo.db` byte-identical entre execuções (mesma seed, mesmo timestamp
âncora, mesma ordem de inserção). Bypassa `storage.upsert_*` porque essas usam
`datetime.now()`, que quebraria determinismo.
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from faker import Faker

ANCHOR_TIMESTAMP = "2026-08-01T00:00:00+00:00"
DEFAULT_SEED = 42

ANCHOR_DATE = datetime(2026, 8, 1, tzinfo=UTC)
CANCELLATION_RATE = 0.05
ORDERS_PER_WEEK_MEAN = 30
CLAIM_STATUSES = ["opened", "closed", "opened", "closed", "in_dispute"]

# Nichos realistas de vendedor ML. Faker pt_BR não tem provider de categoria
# de e-commerce, e `fake.bs()` retorna inglês (herda do en_US). Lista curada
# preserva o "sabor" pt_BR do dataset no PDF/dashboard.
_CATEGORY_NAMES = [
    "Iluminação",
    "Peças de Moto",
    "Ferramentas Manuais",
    "Eletrônicos",
    "Cosméticos",
    "Casa e Cozinha",
    "Esportes e Fitness",
    "Pet Shop",
    "Escritório",
    "Roupas e Acessórios",
]


def write_row(conn: sqlite3.Connection, table: str, row: dict[str, Any]) -> None:
    """Insere uma linha em `table` com `fetched_at = ANCHOR_TIMESTAMP` fixo.

    Assume que `table` tem coluna `fetched_at TEXT NOT NULL`. Não commita —
    caller decide quando fazer commit em batch. Se `row` já contiver
    `fetched_at`, o valor é descartado — o âncora sempre vence.
    """
    row_with_ts = {**row, "fetched_at": ANCHOR_TIMESTAMP}
    columns = ", ".join(row_with_ts.keys())
    placeholders = ", ".join(["?"] * len(row_with_ts))
    conn.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
        tuple(row_with_ts.values()),
    )


def generate_catalog(
    *, seed: int, n_categories: int, n_products: int
) -> dict[str, list[dict[str, Any]]]:
    """Gera catálogo determinístico de categorias + produtos.

    Categorias vêm de lista curada pt_BR (_CATEGORY_NAMES). Títulos dos
    produtos vêm de `Faker.catch_phrase()` (pt_BR-localizado). Preços via
    `random.Random(seed)` — RNG isolado do Faker (class-level RNG do Faker
    é semeado à parte via `Faker.seed`).
    """
    if n_categories > len(_CATEGORY_NAMES):
        raise ValueError(
            f"n_categories={n_categories} excede a lista curada "
            f"({len(_CATEGORY_NAMES)} nomes disponíveis)"
        )

    Faker.seed(seed)
    fake = Faker("pt_BR")
    rng = random.Random(seed)

    categories = [
        {"category_id": f"MLB-CAT-{i:03d}", "name": _CATEGORY_NAMES[i]} for i in range(n_categories)
    ]
    products = []
    for i in range(n_products):
        category = categories[i % n_categories]
        products.append(
            {
                "item_id": f"MLB{100000 + i}",
                "title": fake.catch_phrase(),
                "category_id": category["category_id"],
                "unit_price": round(rng.uniform(50.0, 800.0), 2),
            }
        )
    return {"categories": categories, "products": products}


def generate_orders(
    *,
    catalog: dict[str, list[dict[str, Any]]],
    seed: int,
    weeks_back: int,
) -> list[dict[str, Any]]:
    """Gera lista de pedidos determinística para as `weeks_back` semanas
    anteriores a `ANCHOR_DATE`.

    Volume: Poisson-like via `rng.gauss` clampado. ~5% cancelamento.
    Cada pedido tem 1-3 itens amostrados do catálogo com peso decrescente
    (produtos com índice menor vendem mais → gera curva ABC natural).
    """
    rng = random.Random(seed)
    products = catalog["products"]
    n_products = len(products)
    weights = [1.0 / (i + 1) for i in range(n_products)]  # zipf-like

    orders: list[dict[str, Any]] = []
    order_id_counter = 1_000_000
    for week_offset in range(weeks_back):
        week_start = ANCHOR_DATE - timedelta(days=(weeks_back - week_offset) * 7)
        n_orders_this_week = max(
            5, int(rng.gauss(ORDERS_PER_WEEK_MEAN, ORDERS_PER_WEEK_MEAN * 0.2))
        )
        for _ in range(n_orders_this_week):
            order_id_counter += 1
            day_offset = rng.randint(0, 6)
            hour = rng.randint(9, 22)
            minute = rng.randint(0, 59)
            date_closed = (
                week_start + timedelta(days=day_offset, hours=hour, minutes=minute)
            ).isoformat()

            n_items = rng.choices([1, 2, 3], weights=[0.7, 0.2, 0.1], k=1)[0]
            selected = rng.choices(products, weights=weights, k=n_items)
            items = [
                {
                    "item_id": p["item_id"],
                    "quantity": rng.randint(1, 3),
                    "unit_price": p["unit_price"],
                }
                for p in selected
            ]
            total = sum(it["quantity"] * it["unit_price"] for it in items)
            marketplace_fee = round(total * 0.12, 2)
            shipping_cost = round(rng.uniform(0.0, 25.0), 2)
            status = "cancelled" if rng.random() < CANCELLATION_RATE else "paid"

            # Ordem das chamadas rng.* aqui embaixo é load-bearing pro determinismo.
            # Inserir/reordenar campos que consomem rng (ex: buyer.id) desloca toda
            # a sequência pra pedidos subsequentes. Alterou? Regere data/demo.db.
            raw = {
                "id": order_id_counter,
                "date_closed": date_closed,
                "status": status,
                "total_amount": round(total, 2),
                "payments": [{"marketplace_fee": marketplace_fee}],
                "shipping": {"list_cost": shipping_cost},
                "buyer": {"id": rng.randint(10_000_000, 99_999_999)},
                "order_items": [
                    {
                        "item": {"id": it["item_id"]},
                        "quantity": it["quantity"],
                        "unit_price": it["unit_price"],
                    }
                    for it in items
                ],
            }
            orders.append(
                {
                    "order_id": order_id_counter,
                    "date_closed": date_closed,
                    "status": status,
                    "total_amount": round(total, 2),
                    "marketplace_fee": marketplace_fee,
                    "shipping_cost": shipping_cost,
                    "buyer_id": raw["buyer"]["id"],
                    "raw_json": json.dumps(raw, sort_keys=True),
                    "items": items,
                }
            )
    return orders


def generate_claims(
    *, orders: list[dict[str, Any]], seed: int, rate: float
) -> list[dict[str, Any]]:
    """Gera claims amostrando `rate` fração dos pedidos pagos."""
    rng = random.Random(seed + 1)  # seed distinta pra não correlacionar
    paid = [o for o in orders if o["status"] == "paid"]
    n_claims = max(1, int(len(paid) * rate))
    sampled = rng.sample(paid, k=min(n_claims, len(paid)))

    claims: list[dict[str, Any]] = []
    for i, order in enumerate(sampled):
        claim_id = 5_000_000 + i
        status = rng.choice(CLAIM_STATUSES)
        # date_created = date_closed + 1-14 dias
        base = datetime.fromisoformat(order["date_closed"])
        date_created = (base + timedelta(days=rng.randint(1, 14))).isoformat()
        raw = {
            "id": claim_id,
            "resource_id": order["order_id"],
            "status": status,
            "date_created": date_created,
        }
        claims.append({
            "claim_id": claim_id,
            "order_id": order["order_id"],
            "status": status,
            "date_created": date_created,
            "raw_json": json.dumps(raw, sort_keys=True),
        })
    return claims

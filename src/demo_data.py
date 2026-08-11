"""Gerador de dados sintéticos determinístico para o SellerPulse.

Gera `data/demo.db` byte-identical entre execuções (mesma seed, mesmo timestamp
âncora, mesma ordem de inserção). Bypassa `storage.upsert_*` porque essas usam
`datetime.now()`, que quebraria determinismo.
"""

from __future__ import annotations

import random
import sqlite3
from typing import Any

from faker import Faker

ANCHOR_TIMESTAMP = "2026-08-01T00:00:00+00:00"
DEFAULT_SEED = 42


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

    Nomes vem do Faker (locale pt_BR) com seed fixa. Cada produto é
    associado a uma categoria via módulo do índice.
    """
    rng = random.Random(seed)
    fake = Faker("pt_BR")
    Faker.seed(seed)

    categories = [
        {"category_id": f"MLB-CAT-{i:03d}", "name": fake.bs().title()} for i in range(n_categories)
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

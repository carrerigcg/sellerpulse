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

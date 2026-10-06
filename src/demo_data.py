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
from pathlib import Path
from typing import Any

from faker import Faker

from src.storage import SCHEMA_VERSION, connect

ANCHOR_TIMESTAMP = "2026-08-01T00:00:00+00:00"
DEFAULT_SEED = 42

ANCHOR_DATE = datetime(2026, 8, 1, tzinfo=UTC)
CANCELLATION_RATE = 0.05
ORDERS_PER_WEEK_MEAN = 30
# Recompra: fracao dos pedidos que vai pra quem ja comprou, e quantos
# pedidos pra tras conta como "recente". Os dois sairam de medicao, nao do
# papel -- varri 0.45 a 0.90 contra 60 e 150 e olhei os seis cartoes da tela
# de Clientes em cada combinacao (ver `_pick_buyer`). Mexer aqui muda a cara
# daquela tela inteira, entao mexa medindo.
REPEAT_BUYER_RATE = 0.60
REPEAT_LOOKBACK = 150
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


def _pick_buyer(rng: random.Random, historico: list[int]) -> int:
    """Devolve o comprador de um pedido. Com probabilidade `REPEAT_BUYER_RATE`
    reaproveita alguem que ja comprou nos ultimos `REPEAT_LOOKBACK` pedidos.

    Por que compradores precisam se repetir
    ---------------------------------------
    O `f_score` do RFM e quintil sobre os valores DISTINTOS de frequencia (ver
    `src.segmentation._score_by_quintile`). Com um comprador novo por pedido
    existe um unico valor distinto -- 1 --, o numero de bins cai pra um e TODO
    mundo recebe `f_score = 1`. Como `Champions` e `Loyal` exigem `f >= 4`, os
    dois segmentos saiam vazios: nao era amostra azarada, era impossivel por
    construcao. A tela de Clientes anunciava R$ 0 em dois dos seis cartoes por
    limite do gerador, nao do produto.

    Por que a janela, e nao o historico inteiro
    -------------------------------------------
    A tela pede ~90 dias, mas o gerador produz 26 semanas. Sorteando entre
    todos os compradores ja vistos, a recompra se espalha pelos seis meses e
    quase ninguem junta duas compras dentro dos 90 dias: medido, `Champions`
    ficava com 2 compradores e `Loyal` com 1, que ao lado de 136 em `New` le
    quase tao mal quanto o zero. Olhando so pro passado recente a recompra se
    concentra -- que e tambem o comportamento de verdade, ja que quem comprou
    mes passado volta mais do que quem comprou em marco.

    Por que entre os DISTINTOS da janela
    ------------------------------------
    `historico` guarda um registro por PEDIDO. Sortear direto nele pesa pelo
    numero de compras e parece atraente ("quem compra, compra mais"), mas
    foge: o comprador sorteado volta pra janela, fica mais provavel, volta de
    novo. Medido com `REPEAT_BUYER_RATE = 0.6`, isso produzia alguem com 36
    pedidos em 26 semanas -- e a 0.8, alguem com 88, numa loja que encolhia
    pra 145 compradores. Um outlier desses nao le como cliente fiel, le como
    bug no dado.

    Deduplicando, cada comprador da janela conta uma vez e o reforco fica
    limitado ao que ele ja tem: comprar de novo so recoloca a pessoa na
    janela, nao multiplica o peso dela. A cauda longa continua existindo
    (maximo de 13 pedidos em 26 semanas, contra media de 2,1), so que sem a
    fuga -- no mesmo ponto de operacao o maximo caiu de 36 pra 13.

    `dict.fromkeys` e nao `set`: a ordem precisa ser estavel entre execucoes,
    senao `rng.choice` escolhe diferente e `data/demo.db` deixa de sair
    byte-identico. A ordem de iteracao de um `set` e detalhe de implementacao;
    a de um `dict` e a de insercao, por especificacao.

    Consome RNG de forma condicional -- `rng.random()` so e chamado quando a
    janela tem gente, ou seja, nunca no primeiro pedido. Deterministico do
    mesmo jeito, mas e mais um motivo pra ordem das chamadas aqui ser
    load-bearing (ver o comentario em `generate_orders`).
    """
    janela = list(dict.fromkeys(historico[-REPEAT_LOOKBACK:]))
    if janela and rng.random() < REPEAT_BUYER_RATE:
        escolhido = rng.choice(janela)
    else:
        escolhido = rng.randint(10_000_000, 99_999_999)
    historico.append(escolhido)
    return escolhido


def generate_orders(
    *,
    catalog: dict[str, list[dict[str, Any]]],
    seed: int,
    weeks_back: int,
    anchor: datetime = ANCHOR_DATE,
) -> list[dict[str, Any]]:
    """Gera lista de pedidos determinística para as `weeks_back` semanas
    anteriores a `anchor`.

    Volume: Poisson-like via `rng.gauss` clampado. ~5% cancelamento.
    Cada pedido tem 1-3 itens amostrados do catálogo com peso decrescente
    (produtos com índice menor vendem mais → gera curva ABC natural).

    Compradores se repetem: `REPEAT_BUYER_RATE` dos pedidos vai pra alguém
    que já comprou (ver `_pick_buyer`). Sem isso a análise RFM não tem o que
    segmentar — todo comprador teria frequência 1.

    Por que `anchor` tem default em vez de ser obrigatório: `data/demo.db` é
    versionado no repo e tem que sair byte-idêntico a cada `regerar-dados`
    (ver `generate_demo_db`), e `tests/test_pdf_renderer/` guarda um golden
    HTML que depende destes números exatos. Passar `datetime.now()` como
    default faria os dois divergirem a cada execução. Quem precisa de dado
    "até hoje" — o seller de demonstração no Postgres — passa `anchor`
    explicitamente; o default existe pra manter congelado tudo que é
    comparado contra arquivo commitado. NÃO troque o default por `now()`.

    Só as DATAS dependem de `anchor`. `order_id` vem de `order_id_counter`,
    derivado da sequência do RNG — dois anchors diferentes produzem os MESMOS
    order_ids. Isso é o que torna o `ON CONFLICT DO NOTHING` do
    `backend/seed.py` inútil pra refresh (ver `backend/demo_refresh.py`).
    """
    rng = random.Random(seed)
    products = catalog["products"]
    n_products = len(products)
    weights = [1.0 / (i + 1) for i in range(n_products)]  # zipf-like

    orders: list[dict[str, Any]] = []
    # Local, e nao de modulo: duas chamadas com a mesma seed tem que sair
    # iguais, e um historico compartilhado faria a segunda herdar a primeira.
    buyer_historico: list[int] = []
    order_id_counter = 1_000_000
    for week_offset in range(weeks_back):
        week_start = anchor - timedelta(days=(weeks_back - week_offset) * 7)
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
                "buyer": {"id": _pick_buyer(rng, buyer_historico)},
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
    # `seed + 1` é reservado pra claims — decorrelaciona do generate_orders.
    # Novos geradores devem usar seeds fora da série `seed, seed+1`.
    rng = random.Random(seed + 1)
    paid = [o for o in orders if o["status"] == "paid"]
    # Floor de 1 dispara quando `paid` é não-vazio mas rate * len(paid) < 1
    # (protege que a análise de reputação sempre tenha algo pra mostrar).
    # Se `paid` é vazio, `min()` abaixo zera k e retornamos [].
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
        claims.append(
            {
                "claim_id": claim_id,
                "order_id": order["order_id"],
                "status": status,
                "date_created": date_created,
                "raw_json": json.dumps(raw, sort_keys=True),
            }
        )
    return claims


def generate_demo_db(db_path: Path | str) -> None:
    """Gera SQLite completo em `db_path`. Byte-identical entre execuções.

    Ordem determinística:
    1. Deleta o arquivo se existir (garante inserção sequencial idêntica).
    2. Inicializa schema via `storage.connect` (que também aplica PRAGMAs).
    3. Insere categorias → items_cache → orders + order_items → claims.
    4. Grava `runs` sintético "ok" com timestamp âncora.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    conn = connect(db_path)
    try:
        # `init_schema` stores `datetime.now()` in schema_version.applied_at.
        # Overwrite it with the anchor so the entire file is content-deterministic.
        conn.execute(
            "UPDATE schema_version SET applied_at = ? WHERE version = ?",
            (ANCHOR_TIMESTAMP, SCHEMA_VERSION),
        )
        conn.commit()

        catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
        orders = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=12)
        claims = generate_claims(orders=orders, seed=DEFAULT_SEED, rate=0.04)

        for cat in catalog["categories"]:
            write_row(
                conn,
                "categories_cache",
                {
                    "category_id": cat["category_id"],
                    "name": cat["name"],
                },
            )
        for prod in catalog["products"]:
            write_row(
                conn,
                "items_cache",
                {
                    "item_id": prod["item_id"],
                    "title": prod["title"],
                    "category_id": prod["category_id"],
                },
            )
        for order in orders:
            write_row(
                conn,
                "orders",
                {
                    "order_id": order["order_id"],
                    "date_closed": order["date_closed"],
                    "status": order["status"],
                    "total_amount": order["total_amount"],
                    "marketplace_fee": order["marketplace_fee"],
                    "shipping_cost": order["shipping_cost"],
                    "buyer_id": order["buyer_id"],
                    "raw_json": order["raw_json"],
                },
            )
            # Collapse duplicate item_ids within the same order (rng.choices can
            # pick the same product twice). The schema enforces UNIQUE (order_id,
            # item_id) so we merge by summing quantities; unit_price is identical
            # for the same product.
            seen_items: dict[str, dict] = {}
            for item in order["items"]:
                if item["item_id"] in seen_items:
                    seen_items[item["item_id"]]["quantity"] += item["quantity"]
                else:
                    seen_items[item["item_id"]] = dict(item)
            for item in seen_items.values():
                conn.execute(
                    "INSERT INTO order_items (order_id, item_id, quantity, unit_price) "
                    "VALUES (?, ?, ?, ?)",
                    (order["order_id"], item["item_id"], item["quantity"], item["unit_price"]),
                )
        for c in claims:
            write_row(
                conn,
                "claims",
                {
                    "claim_id": c["claim_id"],
                    "order_id": c["order_id"],
                    "status": c["status"],
                    "date_created": c["date_created"],
                    "raw_json": c["raw_json"],
                },
            )
        # runs sintético
        conn.execute(
            "INSERT INTO runs (run_at, week_start, week_end, pdf_path, status, error_message) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ANCHOR_TIMESTAMP, "2026-07-25", "2026-08-01", None, "ok", None),
        )
        conn.commit()
    finally:
        conn.close()

    # SQLite grava metadata mutável (change_counter, etc.) — vacuum reset
    # produz arquivo byte-idêntico entre runs. Segunda conexão pra não colidir
    # com o try/finally acima; try/finally aqui evita lock de arquivo no
    # Windows se VACUUM levantar.
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("VACUUM")
    finally:
        conn.close()

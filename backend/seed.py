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

Essa idempotencia serve pra nao duplicar, e NAO pra atualizar: re-semear com
outra `anchor` e um no-op silencioso (os `order_id` nao dependem das datas).
Quem precisa mover as datas de um seller ja semeado usa
`backend/demo_refresh.py`.

Tudo roda dentro de uma unica transacao: ou o seller fica totalmente semeado,
ou (em caso de erro) nada e gravado.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta
from typing import Any

from backend.analytics._common import _parse_boundary
from src.demo_data import DEFAULT_SEED, generate_catalog, generate_claims, generate_orders

_TABELAS = (
    "categories",
    "items",
    "orders",
    "order_items",
    "claims",
    "product_costs",
    "item_visits",
)

_TABELA_SQL = {
    "categories": "categories_cache",
    "items": "items_cache",
    "orders": "orders",
    "order_items": "order_items",
    "claims": "claims",
    "product_costs": "product_costs",
    "item_visits": "item_visits",
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

_INSERT_PRODUCT_COST = """
    INSERT INTO product_costs (seller_id, item_id, vigente_desde, custo_unitario)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (seller_id, item_id, vigente_desde) DO NOTHING
"""

_INSERT_VISITA = """
    INSERT INTO item_visits (seller_id, item_id, dia, visitas)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (seller_id, item_id, dia) DO NOTHING
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


# Fatia dos produtos deixada DE PROPOSITO sem custo informado.
#
# Semear 100% faria o indicador de cobertura nunca aparecer, e ele e parte do
# que a demonstracao precisa mostrar: a promessa do produto nao e "temos a
# margem", e "nunca apresentamos um numero incompleto como completo". Com uns
# poucos produtos vazios, a vitrine exibe a feature funcionando em vez de
# esconde-la — e e o estado real de qualquer vendedor, que nunca preenche tudo.
_FATIA_SEM_CUSTO = 0.10

# Custo entre 35% e 62% do preco de venda. Depois da comissao do ML (~12%) e do
# frete, sobra uma margem de contribuicao plausivel para marketplace.
_CUSTO_MIN, _CUSTO_MAX = 0.35, 0.62


def _sorteio_estavel(item_id: str, tempero: str) -> float:
    """Fracao em [0, 1) derivada do item_id. Estavel entre processos.

    `hash()` de string NAO serve: o Python o randomiza por processo (PYTHONHASHSEED),
    entao a demo mudaria de custo a cada reinicio do Render.

    Nao usa o `random.Random(seed)` do gerador de proposito. Aquele RNG e
    consumido em sequencia por `generate_catalog`; pedir mais um numero dentro
    do laco deslocaria o fluxo e TODO preco seguinte mudaria — a demo inteira
    viraria outra, sem que nada falhasse.
    """
    digest = hashlib.sha256(f"{tempero}:{item_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32


def custo_de_demonstracao(item_id: str, unit_price: float) -> float | None:
    """Custo sintetico do produto, ou `None` para os deixados sem custo."""
    if _sorteio_estavel(item_id, "cobertura") < _FATIA_SEM_CUSTO:
        return None
    fracao = _CUSTO_MIN + _sorteio_estavel(item_id, "custo") * (_CUSTO_MAX - _CUSTO_MIN)
    return round(unit_price * fracao, 2)


# Fatia dos produtos deixada DE PROPOSITO sem visita colhida, pelo mesmo
# motivo da fatia sem custo: a demonstracao precisa mostrar o estado "—", que
# e o que distingue "nao medimos" de "medimos e deu zero". Com tudo preenchido
# essa distincao -- que e metade do valor da feature -- ficaria invisivel.
_FATIA_SEM_VISITA = 0.10

# Faixa de conversao por produto. 1% a 9% cobre o que se ve em marketplace:
# anuncio bom converte perto de 5%, anuncio caro ou mal fotografado fica em 1%.
_CONVERSAO_MIN, _CONVERSAO_MAX = 0.01, 0.09

# Os dois ultimos dias saem subcontados DE PROPOSITO, na mesma proporcao que o
# ML entrega antes de consolidar. Assim o aviso que a tela mostra corresponde a
# algo real na demonstracao, em vez de ser um texto decorativo.
_FATOR_DIAS_NAO_CONSOLIDADOS = 0.4

# Quantos dias do fim da serie saem subcontados. Mesmo numero que
# backend/ml/visitas_pg.DIAS_DE_BORDA, e pela mesma razao fisica.
_DIAS_NAO_CONSOLIDADOS = 2


def visitas_de_demonstracao(
    orders: list[dict[str, Any]], *, hoje: date
) -> list[tuple[str, date, int]]:
    """Visitas sinteticas por (item, dia), derivadas dos pedidos gerados.

    Nao mexe em `data/demo.db`: a camada SQLite esta congelada e a linha
    Streamlit, encerrada. Derivar aqui deixa o arquivo intocado e o golden do
    PDF junto -- o custo de produto foi semeado do mesmo jeito, pela mesma
    razao.

    Cada item ganha uma taxa de conversao estavel, e as visitas do dia saem de
    `unidades / taxa`, mais um ruido de quem olhou e nao comprou. Dia sem venda
    tambem tem visita: produto e visto sem ser comprado, que e justamente o
    caso que a feature existe pra revelar.
    """
    unidades_por_item_dia: dict[tuple[str, date], int] = {}
    for pedido in orders:
        if pedido["status"] != "paid":
            continue
        dia = _parse_boundary(pedido["date_closed"]).date()
        for item in _dedupe_order_items(pedido["items"]):
            chave = (item["item_id"], dia)
            unidades_por_item_dia[chave] = unidades_por_item_dia.get(chave, 0) + item["quantity"]

    dias_mudos = {hoje - timedelta(days=n) for n in range(_DIAS_NAO_CONSOLIDADOS)}
    linhas: list[tuple[str, date, int]] = []
    for (item_id, dia), unidades in sorted(unidades_por_item_dia.items()):
        if _sorteio_estavel(item_id, "visita") < _FATIA_SEM_VISITA:
            continue
        taxa = _CONVERSAO_MIN + _sorteio_estavel(item_id, "conversao") * (
            _CONVERSAO_MAX - _CONVERSAO_MIN
        )
        ruido = int(_sorteio_estavel(f"{item_id}:{dia}", "ruido") * 12)
        visitas = max(1, round(unidades / taxa) + ruido)
        if dia in dias_mudos:
            visitas = max(1, round(visitas * _FATOR_DIAS_NAO_CONSOLIDADOS))
        linhas.append((item_id, dia, visitas))
    return linhas


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
    anchor: datetime | None = None,
) -> dict[str, int]:
    """Popula `seller_id` com catalogo + pedidos + claims sinteticos.

    Args:
        pool: pool asyncpg (`backend.db.get_pool()`).
        seller_id: UUID do seller a popular -- precisa ja existir em `sellers`.
        seed: semente do gerador determinístico (default `DEFAULT_SEED` de
            `src/demo_data.py`, a mesma usada pelo `data/demo.db`).
        n_categories, n_products, weeks_back, claim_rate: repassados direto
            pra `generate_catalog` / `generate_orders` / `generate_claims`.
        anchor: data final da serie gerada. `None` (default) usa a ancora
            congelada do `generate_orders` -- a mesma do `data/demo.db`. O
            refresh do seller de demonstracao (`backend/demo_refresh.py`)
            passa `now()` pra que a demo publica termine HOJE.

    Returns:
        dict com as contagens de linhas efetivamente INSERIDAS nesta chamada
        (chaves: categories, items, orders, order_items, claims). Numa
        segunda chamada com os mesmos parametros, todas as contagens vem 0 —
        o `ON CONFLICT DO NOTHING` torna a operacao idempotente.

        ATENCAO: essa idempotencia NAO vale como refresh. Trocar `anchor` e
        rodar de novo devolve tudo 0 e nao move data nenhuma, porque
        `order_id` deriva da sequencia do RNG e nao das datas -- os ids
        colidem e todo INSERT cai no `DO NOTHING`. Pra atualizar as datas de
        um seller ja semeado use `demo_refresh.regenera_demo`.
    """
    async with pool.acquire() as conn, conn.transaction():
        return await seed_na_conexao(
            conn,
            seller_id,
            seed=seed,
            n_categories=n_categories,
            n_products=n_products,
            weeks_back=weeks_back,
            claim_rate=claim_rate,
            anchor=anchor,
        )


async def seed_na_conexao(
    conn,
    seller_id,
    *,
    seed: int = DEFAULT_SEED,
    n_categories: int = 10,
    n_products: int = 50,
    weeks_back: int = 12,
    claim_rate: float = 0.04,
    anchor: datetime | None = None,
) -> dict[str, int]:
    """Mesmo trabalho de `seed_postgres`, mas na conexao/transacao do caller.

    Existe pro `demo_refresh.regenera_demo`, que precisa dos DELETEs e do seed
    na MESMA transacao -- se ele chamasse `seed_postgres`, o seed abriria
    transacao propria numa conexao propria do pool e uma falha no meio deixaria
    a demo publica vazia. Nao abre nem commita transacao: quem chama decide.
    """
    catalog = generate_catalog(seed=seed, n_categories=n_categories, n_products=n_products)
    # `anchor=None` nao pode ser repassado adiante: o default de
    # `generate_orders` e a ancora congelada, nao None.
    extras = {} if anchor is None else {"anchor": anchor}
    orders = generate_orders(catalog=catalog, seed=seed, weeks_back=weeks_back, **extras)
    claims = generate_claims(orders=orders, seed=seed, rate=claim_rate)

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

    # Vigencia um dia ANTES do pedido mais antigo: o custo precisa valer para
    # a janela inteira que a demo exibe. Com vigencia dentro da janela, os
    # primeiros dias apareceriam descobertos e a cobertura ficaria baixa por
    # um motivo que nao diz nada sobre a feature.
    primeiro_pedido = min(_parse_boundary(o["date_closed"]) for o in orders)
    vigencia = (primeiro_pedido - timedelta(days=1)).date()
    custos_args = [
        (seller_id, prod["item_id"], vigencia, custo)
        for prod in catalog["products"]
        if (custo := custo_de_demonstracao(prod["item_id"], prod["unit_price"])) is not None
    ]
    await conn.executemany(_INSERT_PRODUCT_COST, custos_args)

    # As visitas sao derivadas dos pedidos que acabaram de ser gerados, entao
    # o "hoje" delas e o fim da serie -- nao `date.today()`. Com ancora
    # congelada (o `data/demo.db`), usar hoje poria os dias subcontados fora
    # da serie e o efeito nao apareceria.
    ultimo_dia = max(_parse_boundary(o["date_closed"]).date() for o in orders)
    visitas_args = [
        (seller_id, item_id, dia, visitas)
        for item_id, dia, visitas in visitas_de_demonstracao(orders, hoje=ultimo_dia)
    ]
    await conn.executemany(_INSERT_VISITA, visitas_args)

    contagens_depois = await _contagens(conn, seller_id)
    return {chave: contagens_depois[chave] - contagens_antes[chave] for chave in _TABELAS}

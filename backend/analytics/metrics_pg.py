"""Porte de `src/metrics.py` pra Postgres/asyncpg (multi-tenant).

Por que este módulo existe separado de `src/metrics.py`: aquele módulo usa
`pd.read_sql_query`, que exige uma conexão DBAPI2 síncrona (SQLite via
`sqlite3`). `asyncpg` é assíncrono e não implementa essa interface — não dá
pra compartilhar a mesma função com um parâmetro de dialeto, porque o
padrão de chamada (sync vs. await) já é incompatível na raiz. Por isso as
funções aqui são reescritas com `pool.fetch(...)` + montagem manual do
DataFrame, mantendo as mesmas colunas, ordem e arredondamento do original.

Duas armadilhas de tradução de dialeto que este módulo trata explicitamente:

1. Schema multi-tenant: as tabelas usam chave composta (seller_id, ...).
   Todo JOIN casa também por `seller_id`, e toda query filtra
   `seller_id = $1` — senão dados de vendedores diferentes se misturam.
2. `numeric` do Postgres volta como `decimal.Decimal` via asyncpg. Colunas
   numéricas são convertidas pra `float` explicitamente ao montar o
   DataFrame, senão o dtype vira `object` e quebra downstream (gráficos,
   serialização).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pandas as pd

from src.metrics import COST_ESTIMATE_RATE

_FLUXO_COLUMNS = ["date", "receita_bruta", "taxas_ml", "frete", "custo_estimado", "liquido"]
_PRODUTOS_COLUMNS = ["item_id", "title", "category_name", "unidades", "receita"]
_CATEGORIAS_COLUMNS = ["category_id", "category_name", "unidades", "receita"]

_FLUXO_QUERY = """
    SELECT
        -- to_char sobre timestamptz converte pro fuso da SESSAO. O pool ja
        -- fixa server_settings={"timezone": "UTC"}, mas o AT TIME ZONE torna
        -- essa query correta por si so, independente de config externa.
        to_char(date_closed AT TIME ZONE 'UTC', 'YYYY-MM-DD') AS date,
        SUM(total_amount)                  AS receita_bruta,
        SUM(marketplace_fee)               AS taxas_ml,
        SUM(shipping_cost)                 AS frete
    FROM orders
    WHERE seller_id = $1
      AND status = 'paid'
      AND date_closed >= $2::timestamptz
      AND date_closed <  $3::timestamptz
    GROUP BY 1
    ORDER BY date
"""

_TOP_PRODUTOS_QUERY = """
    SELECT
        oi.item_id                                 AS item_id,
        ic.title                                    AS title,
        cc.name                                     AS category_name,
        SUM(oi.quantity)                            AS unidades,
        ROUND(SUM(oi.quantity * oi.unit_price), 2)  AS receita
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    JOIN items_cache ic
      ON ic.seller_id = oi.seller_id AND ic.item_id = oi.item_id
    JOIN categories_cache cc
      ON cc.seller_id = oi.seller_id AND cc.category_id = ic.category_id
    WHERE oi.seller_id = $1
      AND o.status = 'paid'
      AND o.date_closed >= $2::timestamptz
      AND o.date_closed <  $3::timestamptz
    GROUP BY oi.item_id, ic.title, cc.name
    -- Desempate por item_id: divergencia INTENCIONAL de src/metrics.py (que
    -- tem o mesmo defeito de ORDER BY sem desempate, mas esta congelado).
    -- Sem isso, empates de receita tem ordem nao-deterministica no Postgres
    -- e o "top produto" alterna entre recarregamentos com LIMIT.
    ORDER BY receita DESC, oi.item_id
    LIMIT $4
"""

# Segunda query separada — não dá pra reaproveitar o LIMIT do ranking de
# produtos aqui: filtrar por top-N produtos distorceria os totais por
# categoria (excluiria receita de produtos fora do top-N).
_TOP_CATEGORIAS_QUERY = """
    SELECT
        cc.category_id                              AS category_id,
        cc.name                                      AS category_name,
        SUM(oi.quantity)                             AS unidades,
        ROUND(SUM(oi.quantity * oi.unit_price), 2)   AS receita
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    JOIN items_cache ic
      ON ic.seller_id = oi.seller_id AND ic.item_id = oi.item_id
    JOIN categories_cache cc
      ON cc.seller_id = oi.seller_id AND cc.category_id = ic.category_id
    WHERE oi.seller_id = $1
      AND o.status = 'paid'
      AND o.date_closed >= $2::timestamptz
      AND o.date_closed <  $3::timestamptz
    GROUP BY cc.category_id, cc.name
    -- Desempate por category_id: mesma divergencia INTENCIONAL de
    -- src/metrics.py explicada acima em _TOP_PRODUTOS_QUERY.
    ORDER BY receita DESC, cc.category_id
    LIMIT $4
"""


def _parse_boundary(date_str: str) -> datetime:
    """Converte data/hora ISO 8601 em datetime timezone-aware (default UTC).

    asyncpg exige `datetime.datetime` — não `str` — como argumento pra um
    parâmetro com cast `::timestamptz` (o protocolo binário não faz o parse
    que o `psycopg`/SQLite fariam com uma string crua). Datas sem horário
    (ex: "2026-07-25") viram meia-noite UTC, coerente com o pool fixado em
    UTC e com o corte exclusivo de `date_to` nos testes de borda.
    """
    dt = datetime.fromisoformat(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


async def fluxo_financeiro(
    pool, seller_id: uuid.UUID, date_from: str, date_to: str
) -> pd.DataFrame:
    """DataFrame por dia com receita, custos e líquido para a janela dada.

    Args:
        pool: pool asyncpg (`backend.db.get_pool()`).
        seller_id: UUID do seller — isola os dados desse tenant.
        date_from: início inclusivo (ISO 8601, ex: "2026-07-25").
        date_to: fim exclusivo (ISO 8601).

    Returns:
        DataFrame com colunas: date, receita_bruta, taxas_ml, frete,
        custo_estimado, liquido. Uma linha por dia com pedidos pagos.
        Vazio se nenhum pedido no range.
    """
    rows = await pool.fetch(
        _FLUXO_QUERY, seller_id, _parse_boundary(date_from), _parse_boundary(date_to)
    )

    if not rows:
        return pd.DataFrame(columns=_FLUXO_COLUMNS)

    df = pd.DataFrame([dict(r) for r in rows])
    for col in ("receita_bruta", "taxas_ml", "frete"):
        df[col] = df[col].astype(float)

    df["custo_estimado"] = (df["receita_bruta"] * COST_ESTIMATE_RATE).round(2)
    df["liquido"] = (
        df["receita_bruta"] - df["taxas_ml"] - df["frete"] - df["custo_estimado"]
    ).round(2)

    return df[_FLUXO_COLUMNS]


async def top_produtos(
    pool, seller_id: uuid.UUID, date_from: str, date_to: str, n: int = 10
) -> dict[str, pd.DataFrame]:
    """Top N produtos e top N categorias por receita.

    Args:
        pool: pool asyncpg (`backend.db.get_pool()`).
        seller_id: UUID do seller — isola os dados desse tenant.
        date_from: início inclusivo (ISO 8601).
        date_to: fim exclusivo.
        n: número de linhas retornadas em cada ranking. Default 10.

    Returns:
        dict com chaves:
        - "produtos": DataFrame [item_id, title, category_name, unidades, receita]
        - "categorias": DataFrame [category_id, category_name, unidades, receita]
        Ambos ordenados por receita desc.
    """
    dt_from = _parse_boundary(date_from)
    dt_to = _parse_boundary(date_to)
    produtos_rows = await pool.fetch(_TOP_PRODUTOS_QUERY, seller_id, dt_from, dt_to, n)
    categorias_rows = await pool.fetch(_TOP_CATEGORIAS_QUERY, seller_id, dt_from, dt_to, n)

    if produtos_rows:
        produtos = pd.DataFrame([dict(r) for r in produtos_rows])
        produtos["receita"] = produtos["receita"].astype(float)
        produtos = produtos[_PRODUTOS_COLUMNS]
    else:
        produtos = pd.DataFrame(columns=_PRODUTOS_COLUMNS)

    if categorias_rows:
        categorias = pd.DataFrame([dict(r) for r in categorias_rows])
        categorias["receita"] = categorias["receita"].astype(float)
        categorias = categorias[_CATEGORIAS_COLUMNS]
    else:
        categorias = pd.DataFrame(columns=_CATEGORIAS_COLUMNS)

    return {"produtos": produtos, "categorias": categorias}

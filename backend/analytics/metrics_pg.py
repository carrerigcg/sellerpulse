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
3. Fuso do agrupamento diário: aqui o dia é contado em `FUSO_DO_VENDEDOR`
   (America/Sao_Paulo), não em UTC. Divergência INTENCIONAL de
   `src/metrics.py`, na mesma linha do desempate de `ORDER BY` explicado
   abaixo: lá `date_closed` é string ISO no SQLite e a query usa
   `substr(date_closed, 1, 10)`, sem conversão de fuso nenhuma — não existe
   UTC pra trocar. Aquela camada está congelada na Fase 2, lê um banco de
   demonstração local e serve o Streamlit e o PDF; mexer nela é uma mudança
   diferente e mais arriscada, sem usuário real do outro lado.
"""

from __future__ import annotations

import uuid

import pandas as pd

from backend.analytics._common import FUSO_DO_VENDEDOR, _parse_boundary

# `SEM_CATEGORIA` e reexportado daqui: `src/metrics.py` passou a precisar do
# mesmo rotulo quando levou a mesma correcao de LEFT JOIN, e duas copias da
# string em duas camadas e exatamente como as camadas divergem. O import
# re-liga o nome neste namespace, entao quem ja importava
# `backend.analytics.metrics_pg.SEM_CATEGORIA` continua funcionando.
from src.metrics import SEM_CATEGORIA

# Nao existe custo estimado aqui, e nao deve voltar a existir: esta camada
# espelha `src/metrics.py`, onde o comentario do topo explica por que o
# percentual de COGS de 55% foi removido em vez de renomeado. A conta e
# margem de contribuicao = receita_bruta - taxas_ml - frete, as tres parcelas
# vindas de colunas de `orders`.
_FLUXO_COLUMNS = ["date", "receita_bruta", "taxas_ml", "frete", "margem_contribuicao"]
_PRODUTOS_COLUMNS = ["item_id", "title", "category_name", "unidades", "receita"]
_CATEGORIAS_COLUMNS = ["category_id", "category_name", "unidades", "receita"]

# O fuso entra por f-string (nao por parametro $n) porque e constante do
# proprio codigo, nao entrada de usuario: nao ha superficie de injecao, e a
# query continua legivel pra quem for ler o SQL.
_FLUXO_QUERY = f"""
    SELECT
        -- to_char sobre timestamptz converte pro fuso da SESSAO. O pool ja
        -- fixa server_settings={{"timezone": "UTC"}}, mas o AT TIME ZONE
        -- explicito torna essa query correta por si so, independente de
        -- config externa -- e, agora, o fuso declarado aqui e o do VENDEDOR
        -- (America/Sao_Paulo): o dia do grafico tem que ser o dia em que ele
        -- conta a venda, nao o dia UTC. Ver FUSO_DO_VENDEDOR em _common.py.
        to_char(date_closed AT TIME ZONE '{FUSO_DO_VENDEDOR}', 'YYYY-MM-DD') AS date,
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
        -- LEFT JOIN nos dois caches: item sem linha em items_cache e anuncio
        -- apagado (a ingestao leva 404 e nunca cacheia). Foi vendido e a
        -- receita e real, entao ele fica no ranking: o SKU e o titulo de
        -- fallback. Com INNER JOIN ele sumia junto com o dinheiro (11,2% numa
        -- loja real) e esta tela divergia da Executive.
        COALESCE(ic.title, oi.item_id)              AS title,
        -- Categoria desconhecida e DESCONHECIDA: rotulo explicito ($5), nunca
        -- uma categoria real emprestada. Ver _TOP_CATEGORIAS_QUERY.
        COALESCE(cc.name, $5)                       AS category_name,
        SUM(oi.quantity)                            AS unidades,
        ROUND(SUM(oi.quantity * oi.unit_price), 2)  AS receita
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    LEFT JOIN items_cache ic
      ON ic.seller_id = oi.seller_id AND ic.item_id = oi.item_id
    LEFT JOIN categories_cache cc
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
#
# Item sem categoria conhecida (anuncio apagado, ou categoria que nao entrou
# em categories_cache) NAO some e NAO e jogado numa categoria real: os dois
# erros corrompem o breakdown (o primeiro faz a soma das categorias nao bater
# com a receita total; o segundo atribui venda a quem nao vendeu). Ele forma
# um balde proprio, com category_id NULL (nenhum id real do ML colide) e o
# rotulo SEM_CATEGORIA ($5). Agrupar so por cc.* junta todos os desconhecidos
# num balde unico.
_TOP_CATEGORIAS_QUERY = """
    SELECT
        cc.category_id                              AS category_id,
        COALESCE(cc.name, $5)                        AS category_name,
        SUM(oi.quantity)                             AS unidades,
        ROUND(SUM(oi.quantity * oi.unit_price), 2)   AS receita
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    LEFT JOIN items_cache ic
      ON ic.seller_id = oi.seller_id AND ic.item_id = oi.item_id
    LEFT JOIN categories_cache cc
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


async def fluxo_financeiro(
    pool, seller_id: uuid.UUID, date_from: str, date_to: str
) -> pd.DataFrame:
    """DataFrame por dia com receita, custos do ML e margem de contribuição.

    Margem de contribuição = receita_bruta - taxas_ml - frete. Espelha
    `src/metrics.py.fluxo_financeiro`: mesmas colunas, mesma ordem, mesmo
    arredondamento — a paridade é testada em
    `test_fluxo_paridade_com_a_versao_sqlite`.

    Args:
        pool: pool asyncpg (`backend.db.get_pool()`).
        seller_id: UUID do seller — isola os dados desse tenant.
        date_from: início inclusivo (ISO 8601, ex: "2026-07-25").
        date_to: fim exclusivo (ISO 8601).

    Returns:
        DataFrame com colunas: date, receita_bruta, taxas_ml, frete,
        margem_contribuicao. Uma linha por dia com pedidos pagos.
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

    df["margem_contribuicao"] = (df["receita_bruta"] - df["taxas_ml"] - df["frete"]).round(2)

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

        Item vendido sem linha em `items_cache` (anúncio apagado no ML) entra
        normalmente: `title` cai pro próprio item_id e a categoria vira
        `SEM_CATEGORIA`. Em `categorias` ele forma um balde único com
        `category_id` None — assim a soma das categorias fecha com a receita
        total, sem atribuir venda a uma categoria real.
    """
    dt_from = _parse_boundary(date_from)
    dt_to = _parse_boundary(date_to)
    produtos_rows = await pool.fetch(
        _TOP_PRODUTOS_QUERY, seller_id, dt_from, dt_to, n, SEM_CATEGORIA
    )
    categorias_rows = await pool.fetch(
        _TOP_CATEGORIAS_QUERY, seller_id, dt_from, dt_to, n, SEM_CATEGORIA
    )

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

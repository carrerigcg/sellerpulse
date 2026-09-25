"""Porte de `src/segmentation.py` pra Postgres/asyncpg (multi-tenant).

Por que este módulo existe separado de `src/segmentation.py`: aquele módulo
usa `pd.read_sql_query`, que exige uma conexão DBAPI2 síncrona (SQLite via
`sqlite3`). `asyncpg` é assíncrono e não implementa essa interface — não dá
pra compartilhar a mesma função com um parâmetro de dialeto, porque o
padrão de chamada (sync vs. await) já é incompatível na raiz. Por isso as
funções aqui são reescritas com `pool.fetch(...)` + montagem manual do
DataFrame, mantendo as mesmas colunas, ordem e arredondamento do original.

A lógica pura (sem SQL) de `rfm_scores` — `_score_by_quintile` e
`_assign_segment` (que por sua vez usa `_RFM_SEGMENT_RULES`) — é importada
de `src.segmentation` em vez de reimplementada: não há nada específico de
dialeto ali, então duplicar seria só superfície de bug.

Armadilhas de tradução de dialeto tratadas explicitamente aqui:

1. Schema multi-tenant: as tabelas usam chave composta (seller_id, ...).
   Todo JOIN casa também por `seller_id`, e toda query filtra
   `seller_id = $1` — senão dados de vendedores diferentes se misturam ou,
   pior, um `order_id`/`item_id`/`category_id` colidente entre sellers causa
   fan-out (a mesma linha de `order_items` casa com o pedido/item errado de
   outro tenant e a receita multiplica).
2. `numeric` do Postgres volta como `decimal.Decimal` via asyncpg. Colunas
   numéricas são convertidas pra `float` explicitamente ao montar o
   DataFrame.
3. `to_char` sobre `timestamptz` usa o fuso da SESSÃO. Toda formatação de
   mês (`cohort_produto`) usa `AT TIME ZONE 'UTC'` explicitamente — o pool
   já fixa `server_settings={"timezone": "UTC"}`, mas isso torna a query
   correta por si só, independente de config externa.
4. O cálculo de `recency_dias` em `rfm_scores` trunca pra DATA (descarta
   hora), igual ao original em SQLite (`ultima_compra.str[:10]`). Sem essa
   truncagem, uma compra às 14:30 de ontem daria 0 dias de recência em vez
   de 1 — asyncpg devolve `MAX(date_closed)` como `datetime` completo, não
   como string ISO truncada.
"""

from __future__ import annotations

import uuid

import pandas as pd

from backend.analytics._common import _parse_boundary
from src.segmentation import _assign_segment, _score_by_quintile

_ABC_COLUMNS = ["sku", "titulo", "receita", "receita_pct", "receita_acumulada_pct", "classe"]

_RFM_COLUMNS = [
    "buyer_id",
    "recency_dias",
    "frequency",
    "monetary",
    "r_score",
    "f_score",
    "m_score",
    "segmento",
]

_ABC_PARETO_QUERY = """
    SELECT
        oi.item_id                                       AS sku,
        ic.title                                          AS titulo,
        ROUND(SUM(oi.quantity * oi.unit_price), 2)        AS receita
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    JOIN items_cache ic
      ON ic.seller_id = oi.seller_id AND ic.item_id = oi.item_id
    WHERE oi.seller_id = $1
      AND o.status = 'paid'
      AND o.date_closed >= $2::timestamptz
      AND o.date_closed <  $3::timestamptz
    GROUP BY oi.item_id, ic.title
    -- Desempate por sku: divergencia INTENCIONAL de src/segmentation.py
    -- (que tem o mesmo defeito de ORDER BY sem desempate, mas esta
    -- congelado). Sem isso, empates de receita tem ordem nao-deterministica
    -- no Postgres e a classe A/B/C (que depende da ordem acumulada) podia
    -- variar entre recarregamentos.
    ORDER BY receita DESC, oi.item_id
"""

_RFM_BASE_QUERY = """
    SELECT
        buyer_id,
        MAX(date_closed)            AS ultima_compra,
        COUNT(*)                    AS frequency,
        ROUND(SUM(total_amount), 2) AS monetary
    FROM orders
    WHERE seller_id = $1
      AND status = 'paid'
      AND buyer_id IS NOT NULL
      AND date_closed >= $2::timestamptz
      AND date_closed <  $3::timestamptz
    GROUP BY buyer_id
    -- ORDER BY adicionado (o original nao tem nenhum): GROUP BY sem ORDER
    -- BY nao e deterministico no Postgres (hash aggregate). Divergencia
    -- INTENCIONAL de src/segmentation.py -- nao afeta os valores, so a
    -- ordem das linhas.
    ORDER BY buyer_id
"""

# "Mes de lancamento" = menor date_closed do item NO BANCO INTEIRO (sem
# filtro de janela), igual ao original. AT TIME ZONE 'UTC' explicito porque
# to_char sobre timestamptz usa o fuso da sessao.
_COHORT_LAUNCH_QUERY = """
    SELECT
        oi.item_id,
        to_char(MIN(o.date_closed) AT TIME ZONE 'UTC', 'YYYY-MM') AS mes_lancamento
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    WHERE oi.seller_id = $1
      AND o.status = 'paid'
    GROUP BY oi.item_id
"""

_COHORT_REVENUE_QUERY = """
    SELECT
        oi.item_id,
        to_char(o.date_closed AT TIME ZONE 'UTC', 'YYYY-MM')     AS mes_corrente,
        ROUND(SUM(oi.quantity * oi.unit_price), 2)               AS receita
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    WHERE oi.seller_id = $1
      AND o.status = 'paid'
      AND o.date_closed >= $2::timestamptz
      AND o.date_closed <  $3::timestamptz
    GROUP BY oi.item_id, mes_corrente
"""


async def abc_pareto(pool, seller_id: uuid.UUID, date_from: str, date_to: str) -> pd.DataFrame:
    """Ranking de produtos por receita + classe A/B/C (regra 80/15/5 acumulada).

    Args:
        pool: pool asyncpg (`backend.db.get_pool()`).
        seller_id: UUID do seller — isola os dados desse tenant.
        date_from: início inclusivo (ISO 8601).
        date_to: fim exclusivo (ISO 8601).

    Returns:
        DataFrame ordenado por receita desc com colunas:
        sku, titulo, receita, receita_pct, receita_acumulada_pct, classe.
        Vazio (colunas presentes) se período sem dados.

    Regra de classe:
        - A: receita_acumulada_pct <= 80  (produtos "cabeça")
        - B: receita_acumulada_pct <= 95  (intermediários)
        - C: caso contrário               (cauda)
        O produto que cruza a fronteira é incluído na classe superior.
    """
    rows = await pool.fetch(
        _ABC_PARETO_QUERY, seller_id, _parse_boundary(date_from), _parse_boundary(date_to)
    )
    if not rows:
        return pd.DataFrame(columns=_ABC_COLUMNS)

    df = pd.DataFrame([dict(r) for r in rows])
    df["receita"] = df["receita"].astype(float)

    total = df["receita"].sum()
    df["receita_pct"] = (100.0 * df["receita"] / total).round(4)
    df["receita_acumulada_pct"] = df["receita_pct"].cumsum().round(4)

    def _classify(pct_acum: float) -> str:
        if pct_acum <= 80.0:
            return "A"
        if pct_acum <= 95.0:
            return "B"
        return "C"

    df["classe"] = df["receita_acumulada_pct"].apply(_classify)
    return df[_ABC_COLUMNS]


async def rfm_scores(pool, seller_id: uuid.UUID, date_from: str, date_to: str) -> pd.DataFrame:
    """RFM por comprador único no período + segmento textual.

    Args:
        pool: pool asyncpg (`backend.db.get_pool()`).
        seller_id: UUID do seller — isola os dados desse tenant.
        date_from: início inclusivo (ISO 8601).
        date_to: fim exclusivo — usado como "hoje" no cálculo de recency.

    Returns:
        DataFrame com uma linha por buyer_id e colunas:
        buyer_id, recency_dias, frequency, monetary, r_score, f_score,
        m_score, segmento (Champions | Loyal | At Risk | New | Hibernating | Others).

    Scores 1-5 via quintis dentro da base do período. Segmentação por regras
    ordenadas (primeira que casar vence).
    """
    rows = await pool.fetch(
        _RFM_BASE_QUERY, seller_id, _parse_boundary(date_from), _parse_boundary(date_to)
    )
    if not rows:
        return pd.DataFrame(columns=_RFM_COLUMNS)

    df = pd.DataFrame([dict(r) for r in rows])
    df["monetary"] = df["monetary"].astype(float)
    df["frequency"] = df["frequency"].astype(int)

    # Recency em dias — trunca pra DATA em UTC, igual ao original (que usa
    # ultima_compra.str[:10]). asyncpg devolve `ultima_compra` como datetime
    # tz-aware (o pool fixa a sessao em UTC), nao como string ISO: sem
    # truncar aqui, uma compra as 14:30 de ontem daria 0 dias de recencia em
    # vez de 1.
    ultima = pd.to_datetime(df["ultima_compra"], utc=True).dt.tz_localize(None).dt.normalize()
    date_to_ts = pd.Timestamp(date_to[:10])
    df["recency_dias"] = (date_to_ts - ultima).dt.days.astype(int)

    # Scores: recency menor = melhor -> ascending=False (maior recency_dias -> score 1).
    df["r_score"] = _score_by_quintile(df["recency_dias"], ascending=False)
    df["f_score"] = _score_by_quintile(df["frequency"], ascending=True)
    df["m_score"] = _score_by_quintile(df["monetary"], ascending=True)

    df["segmento"] = df.apply(_assign_segment, axis=1)

    return df[_RFM_COLUMNS]


async def cohort_produto(pool, seller_id: uuid.UUID, date_from: str, date_to: str) -> pd.DataFrame:
    """Cohort de produtos por mês de lançamento — agregado.

    "Mês de lançamento" = menor date_closed do produto **no banco inteiro**
    (não apenas na janela). Cada linha do resultado é um grupo de produtos que
    tiveram primeira venda no mesmo mês.

    Args:
        pool: pool asyncpg (`backend.db.get_pool()`).
        seller_id: UUID do seller — isola os dados desse tenant.
        date_from: início inclusivo (ISO 8601).
        date_to: fim exclusivo.

    Returns:
        DataFrame pivot:
        - Index: mes_lancamento (str "YYYY-MM")
        - Columns: mes_corrente (str "YYYY-MM"), ordenadas cronologicamente
        - Values: soma de receita do cohort naquele mês corrente (float)
        - NaN acima da diagonal (mes_corrente < mes_lancamento)
        DataFrame vazio se nenhuma venda no período.
    """
    # 1) Mapa item_id -> mês de lançamento (banco inteiro, não apenas janela).
    launch_rows = await pool.fetch(_COHORT_LAUNCH_QUERY, seller_id)
    if not launch_rows:
        return pd.DataFrame()
    launches = pd.DataFrame([dict(r) for r in launch_rows])

    # 2) Receita por item x mês corrente na janela.
    revenue_rows = await pool.fetch(
        _COHORT_REVENUE_QUERY, seller_id, _parse_boundary(date_from), _parse_boundary(date_to)
    )
    if not revenue_rows:
        return pd.DataFrame()
    revenue = pd.DataFrame([dict(r) for r in revenue_rows])
    revenue["receita"] = revenue["receita"].astype(float)

    # 3) Join + agregação por (mes_lancamento, mes_corrente).
    merged = revenue.merge(launches, on="item_id", how="left")
    agg = (
        merged.groupby(["mes_lancamento", "mes_corrente"], as_index=False)["receita"].sum().round(2)
    )

    # 4) Pivot para o formato triangular.
    pivot = agg.pivot(index="mes_lancamento", columns="mes_corrente", values="receita")
    pivot.index.name = "mes_lancamento"
    pivot.columns.name = "mes_corrente"

    # 5) Garantir ordenação cronológica.
    pivot = pivot.sort_index(axis=0).sort_index(axis=1)

    return pivot

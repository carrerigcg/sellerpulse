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
   mês (`cohort_produto`) declara `AT TIME ZONE` explicitamente — o pool já
   fixa `server_settings={"timezone": "UTC"}`, mas isso torna a query
   correta por si só, independente de config externa. O fuso declarado é o
   do VENDEDOR (`FUSO_DO_VENDEDOR`, America/Sao_Paulo), não UTC: o mês do
   cohort tem que ser o mês em que o vendedor conta a venda. Divergência
   INTENCIONAL de `src/segmentation.py`, que lê SQLite onde `date_closed` é
   string ISO e a query usa `strftime`/`substr` sem conversão de fuso
   nenhuma — lá não existe UTC pra trocar. Aquela camada está congelada na
   Fase 2 e serve o Streamlit e o PDF a partir de um banco de demonstração
   local.
4. O cálculo de `recency_dias` em `rfm_scores` trunca pra DATA (descarta
   hora), igual ao original em SQLite (`ultima_compra.str[:10]`). Sem essa
   truncagem, uma compra às 14:30 de ontem daria 0 dias de recência em vez
   de 1 — asyncpg devolve `MAX(date_closed)` como `datetime` completo, não
   como string ISO truncada. A truncagem acontece no fuso do vendedor pelo
   mesmo motivo do item 3.
"""

from __future__ import annotations

import uuid

import pandas as pd

from backend.analytics._common import FUSO_DO_VENDEDOR, _parse_boundary
from src.segmentation import _assign_segment, _score_by_quintile

_ABC_COLUMNS = [
    "sku",
    "titulo",
    "receita",
    "receita_pct",
    "receita_acumulada_pct",
    "classe",
    "custo_produtos",
    "receita_sem_custo",
    "unidades",
    "visitas",
    "conversao",
]

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

_ABC_PARETO_QUERY = f"""
    -- As visitas entram DEPOIS da agregacao, numa CTE. Visita e por ITEM e
    -- por dia; `order_items` tem uma linha por item por PEDIDO. Juntar antes
    -- do GROUP BY multiplicaria as visitas pelo numero de pedidos daquele
    -- item -- um produto vendido 40 vezes apareceria com 40x as visitas que
    -- teve, e a conversao sairia 40 vezes menor sem nada falhar.
    WITH por_item AS (
    SELECT
        oi.item_id                                       AS sku,
        -- Item sem linha em items_cache = anuncio apagado (a ingestao leva 404
        -- na API de itens e nunca cacheia). Foi vendido e a receita e real,
        -- entao ele fica: o SKU e o titulo de fallback. Com INNER JOIN ele
        -- sumia junto com o dinheiro (11,2% numa loja real) e a tela Produtos
        -- passava a divergir da Executive.
        COALESCE(ic.title, oi.item_id)                    AS titulo,
        ROUND(SUM(oi.quantity * oi.unit_price), 2)        AS receita,
        SUM(oi.quantity)::int                             AS unidades,
        -- Mesmas duas colunas do fluxo financeiro, aqui por produto. Na tela
        -- de Custos e o que diz "este e o produto classe A que ainda nao tem
        -- custo", que e a ordem em que vale a pena preencher.
        ROUND(COALESCE(SUM(oi.quantity * pc.custo_unitario), 0), 2) AS custo_produtos,
        ROUND(
            COALESCE(
                SUM(oi.quantity * oi.unit_price) FILTER (WHERE pc.custo_unitario IS NULL),
                0
            ),
            2
        )                                                 AS receita_sem_custo
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    LEFT JOIN items_cache ic
      ON ic.seller_id = oi.seller_id AND ic.item_id = oi.item_id
    -- Custo vigente na data do pedido. Identico ao de metrics_pg.py, e pela
    -- mesma razao: a data entra no fuso do VENDEDOR, nao em UTC.
    LEFT JOIN LATERAL (
        SELECT c.custo_unitario
          FROM product_costs c
         WHERE c.seller_id = oi.seller_id
           AND c.item_id   = oi.item_id
           AND c.vigente_desde <= (o.date_closed AT TIME ZONE '{FUSO_DO_VENDEDOR}')::date
         ORDER BY c.vigente_desde DESC
         LIMIT 1
    ) pc ON TRUE
    WHERE oi.seller_id = $1
      AND o.status = 'paid'
      AND o.date_closed >= $2::timestamptz
      AND o.date_closed <  $3::timestamptz
    GROUP BY oi.item_id, ic.title
    )
    SELECT
        p.*,
        -- Visitas da janela. `linhas_de_visita` conta TODAS as linhas do item,
        -- dentro ou fora da janela, e e o que distingue "colhemos e deu zero"
        -- de "nunca colhemos". Sem essa distincao um produto sem colheita
        -- apareceria com 0% de conversao, que e uma afirmacao -- e a mesma
        -- regra do custo de produto: ausencia nao e zero.
        COALESCE(v.visitas_na_janela, 0)::int AS visitas,
        COALESCE(v.linhas_de_visita, 0)::int  AS linhas_de_visita
    FROM por_item p
    LEFT JOIN LATERAL (
        SELECT
            SUM(iv.visitas) FILTER (
                WHERE iv.dia >= ($2::timestamptz AT TIME ZONE '{FUSO_DO_VENDEDOR}')::date
                  AND iv.dia <  ($3::timestamptz AT TIME ZONE '{FUSO_DO_VENDEDOR}')::date
            ) AS visitas_na_janela,
            COUNT(*) AS linhas_de_visita
          FROM item_visits iv
         WHERE iv.seller_id = $1 AND iv.item_id = p.sku
    ) v ON TRUE
    -- Desempate por sku: divergencia INTENCIONAL de src/segmentation.py
    -- (que tem o mesmo defeito de ORDER BY sem desempate, mas esta
    -- congelado). Sem isso, empates de receita tem ordem nao-deterministica
    -- no Postgres e a classe A/B/C (que depende da ordem acumulada) podia
    -- variar entre recarregamentos.
    ORDER BY p.receita DESC, p.sku
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
# filtro de janela), igual ao original. AT TIME ZONE explicito porque to_char
# sobre timestamptz usa o fuso da sessao; o fuso e o do VENDEDOR porque o mes
# de lancamento e o mes em que ELE viu a primeira venda (medido na loja real:
# 3 de 744 itens trocam de mes de lancamento entre UTC e Brasilia).
#
# O fuso entra por f-string (nao por parametro $n) porque e constante do
# proprio codigo, nao entrada de usuario: nao ha superficie de injecao.
_COHORT_LAUNCH_QUERY = f"""
    SELECT
        oi.item_id,
        to_char(MIN(o.date_closed) AT TIME ZONE '{FUSO_DO_VENDEDOR}', 'YYYY-MM') AS mes_lancamento
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    WHERE oi.seller_id = $1
      AND o.status = 'paid'
    GROUP BY oi.item_id
"""

# Mesmo fuso do _COHORT_LAUNCH_QUERY -- obrigatoriamente: o pivot cruza
# mes_lancamento com mes_corrente, e dois fusos diferentes nos dois eixos
# colocariam receita acima da diagonal (mes corrente "anterior" ao
# lancamento) em pedidos da virada do dia.
_COHORT_REVENUE_QUERY = f"""
    SELECT
        oi.item_id,
        to_char(o.date_closed AT TIME ZONE '{FUSO_DO_VENDEDOR}', 'YYYY-MM') AS mes_corrente,
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
        sku, titulo, receita, receita_pct, receita_acumulada_pct, classe,
        custo_produtos, receita_sem_custo, unidades, visitas, conversao.

        `visitas` e `None` quando o item nunca teve visita colhida, e 0 quando
        foi colhido e deu zero -- a tela mostra "—" no primeiro caso. Idem
        `conversao`, que e None sem visita para dividir.

        As duas ultimas sao o custo de produto informado pelo vendedor
        (migration 0008), na vigencia que valia na data de cada pedido, e
        quanto da receita do produto veio de venda sem custo informado. Com
        nenhum custo cadastrado as duas sao zero e nada mais muda.
        Vazio (colunas presentes) se período sem dados.

        Item vendido sem linha em `items_cache` (anúncio apagado no ML) entra
        no ranking com o próprio SKU como `titulo`: a receita é real e a
        classe A/B/C tem que ser calculada sobre o total completo.

    Regra de classe:
        - A: receita_acumulada_pct <= 80  (produtos "cabeça")
        - B: receita_acumulada_pct <= 95  (intermediários)
        - C: caso contrário               (cauda)
        A comparação é `<=` sobre a acumulada, que já inclui a receita do
        próprio produto. Então o produto que empurra a acumulada ALÉM de 80
        cai em B, não em A: a fronteira fica logo antes dele, não nele. Na
        demonstração, acumulada 79,4955 é A e a linha seguinte, 80,7894, é B.
    """
    rows = await pool.fetch(
        _ABC_PARETO_QUERY, seller_id, _parse_boundary(date_from), _parse_boundary(date_to)
    )
    if not rows:
        return pd.DataFrame(columns=_ABC_COLUMNS)

    df = pd.DataFrame([dict(r) for r in rows])
    for col in ("receita", "custo_produtos", "receita_sem_custo"):
        df[col] = df[col].astype(float)

    # `visitas` vira None quando o item NUNCA foi colhido, e continua 0 quando
    # foi colhido e deu zero. A distincao e a mesma do custo de produto:
    # ausencia nao e zero, e "0% de conversao" e uma afirmacao que so se pode
    # fazer sobre quem tem visita medida.
    nunca_colhido = df["linhas_de_visita"] == 0
    df["visitas"] = df["visitas"].astype(object).where(~nunca_colhido, None)

    # Conversao = unidades / visitas, em porcentagem.
    #
    # E uma APROXIMACAO, e a tela diz isso: um pedido com tres unidades do
    # mesmo item e uma visita que converteu, nao tres. A metrica honesta seria
    # pedidos/visitas; a util pra quem decide estoque e unidades. Rotulada
    # "conversao (unidades)" na tela -- inventar um numero sem dizer qual e
    # seria repetir o erro do custo estimado.
    def _conversao(linha):
        visitas = linha["visitas"]
        if visitas is None or visitas <= 0:
            return None
        return round(100.0 * linha["unidades"] / visitas, 2)

    df["conversao"] = df.apply(_conversao, axis=1)
    df = df.drop(columns=["linhas_de_visita"])

    total = df["receita"].sum()
    df["receita_pct"] = (100.0 * df["receita"] / total).round(4)
    # Acumulado derivado da receita CRUA, nao do cumsum de `receita_pct`.
    # Somar percentuais ja arredondados acumula o erro de arredondamento linha
    # a linha: num catalogo de centenas de produtos o ultimo valor nao fecha em
    # 100 (medido: 100,0002 no demo, 99,9911 numa loja real de 743 produtos —
    # o desvio vai pros dois lados). O eixo direito do Pareto e 0-100% por
    # definicao, e um valor acima de 100 fazia o Recharts esticar o dominio e
    # rotular o topo como "100.0002".
    df["receita_acumulada_pct"] = (100.0 * df["receita"].cumsum() / total).round(4)

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

    # Recency em dias — trunca pra DATA, igual ao original (que usa
    # ultima_compra.str[:10]). asyncpg devolve `ultima_compra` como datetime
    # tz-aware (o pool fixa a sessao em UTC), nao como string ISO: sem
    # truncar aqui, uma compra as 14:30 de ontem daria 0 dias de recencia em
    # vez de 1. Essa razao continua valendo; o que mudou e ONDE a truncagem
    # acontece.
    #
    # A truncagem e no fuso do VENDEDOR, e os dois lados da subtracao tem que
    # estar nele: `date_to[:10]` e uma data de calendario que o chamador
    # escreveu pensando em Brasilia, e truncar `ultima_compra` em UTC
    # comparava "hoje em Brasilia" com "ontem/hoje em UTC". Medido na loja
    # real: 112 de 780 compradores tinham recency_dias deslocada em 1 dia,
    # todos os da venda da noite (21h-23h BRT viram 00h-02h UTC do dia
    # seguinte).
    ultima = (
        pd.to_datetime(df["ultima_compra"], utc=True)
        .dt.tz_convert(FUSO_DO_VENDEDOR)
        .dt.tz_localize(None)
        .dt.normalize()
    )
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

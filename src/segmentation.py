"""Camada de segmentação — funções puras.

Cada função recebe conexão SQLite + janela temporal e devolve DataFrame.
Sem side effects: leitura pura, sem prints, sem HTTP, sem escrita.
"""

from __future__ import annotations

import sqlite3

import pandas as pd


def abc_pareto(conn: sqlite3.Connection, date_from: str, date_to: str) -> pd.DataFrame:
    """Ranking de produtos por receita + classe A/B/C (regra 80/15/5 acumulada).

    Args:
        conn: conexão SQLite aberta.
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
    query = """
        SELECT
            oi.item_id                                       AS sku,
            ic.title                                          AS titulo,
            ROUND(SUM(oi.quantity * oi.unit_price), 2)        AS receita
        FROM order_items oi
        JOIN orders o        ON o.order_id = oi.order_id
        JOIN items_cache ic  ON ic.item_id = oi.item_id
        WHERE o.status = 'paid'
          AND o.date_closed >= ?
          AND o.date_closed <  ?
        GROUP BY oi.item_id, ic.title
        ORDER BY receita DESC
    """
    df = pd.read_sql_query(query, conn, params=(date_from, date_to))
    empty_cols = ["sku", "titulo", "receita", "receita_pct", "receita_acumulada_pct", "classe"]
    if df.empty:
        return pd.DataFrame(columns=empty_cols)

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
    return df[empty_cols]


# Ordem importa: primeiro segmento cuja condição casar vence.
_RFM_SEGMENT_RULES: list[tuple[str, str]] = [
    ("Champions", "r_score >= 4 and f_score >= 4 and m_score >= 4"),
    ("Loyal", "f_score >= 4 and m_score >= 3"),
    ("At Risk", "r_score <= 2 and (f_score >= 3 or m_score >= 3)"),
    ("New", "r_score >= 4 and f_score <= 2"),
    ("Hibernating", "r_score <= 2 and f_score <= 2 and m_score <= 2"),
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


def _score_by_quintile(series: pd.Series, ascending: bool = True) -> pd.Series:
    """Devolve score int 1-5 via quintis. `ascending=True` = maior valor → score 5.

    Trata cases com < 5 valores distintos via `duplicates="drop"` e labels
    dinâmicos. Empates recebem o mesmo score. NaN não deve ocorrer (série
    numérica não-nula por construção).
    """
    labels_asc = [1, 2, 3, 4, 5]
    labels = labels_asc if ascending else list(reversed(labels_asc))
    # rank(method="first") desempata sequencialmente — evita bins vazios.
    ranks = series.rank(method="first")
    try:
        binned = pd.qcut(ranks, q=5, labels=labels)
    except ValueError:
        # Poucas amostras distintas — cai para menos bins.
        n_bins = min(5, ranks.nunique())
        sub_labels = labels[:n_bins]
        binned = pd.qcut(ranks, q=n_bins, labels=sub_labels, duplicates="drop")
    return binned.astype(int)


def _assign_segment(row: pd.Series) -> str:
    r_score = int(row["r_score"])
    f_score = int(row["f_score"])
    m_score = int(row["m_score"])
    scope = {"r_score": r_score, "f_score": f_score, "m_score": m_score}
    for name, expr in _RFM_SEGMENT_RULES:
        if eval(expr, {"__builtins__": {}}, scope):  # noqa: S307 — expr é hardcoded
            return name
    return "Others"


def rfm_scores(conn: sqlite3.Connection, date_from: str, date_to: str) -> pd.DataFrame:
    """RFM por comprador único no período + segmento textual.

    Args:
        conn: conexão SQLite aberta.
        date_from: início inclusivo (ISO 8601).
        date_to: fim exclusivo — usado como "hoje" no cálculo de recency.

    Returns:
        DataFrame com uma linha por buyer_id e colunas:
        buyer_id, recency_dias, frequency, monetary, r_score, f_score,
        m_score, segmento (Champions | Loyal | At Risk | New | Hibernating | Others).

    Scores 1-5 via quintis dentro da base do período. Segmentação por regras
    ordenadas (primeira que casar vence).
    """
    query = """
        SELECT
            buyer_id,
            MAX(date_closed)         AS ultima_compra,
            COUNT(*)                 AS frequency,
            ROUND(SUM(total_amount), 2) AS monetary
        FROM orders
        WHERE status = 'paid'
          AND buyer_id IS NOT NULL
          AND date_closed >= ?
          AND date_closed <  ?
        GROUP BY buyer_id
    """
    df = pd.read_sql_query(query, conn, params=(date_from, date_to))
    if df.empty:
        return pd.DataFrame(columns=_RFM_COLUMNS)

    # Recency em dias — usa parte de data (10 primeiros chars) de date_to como referência.
    date_to_ts = pd.Timestamp(date_to[:10])
    ultima_ts = pd.to_datetime(df["ultima_compra"].str[:10])
    df["recency_dias"] = (date_to_ts - ultima_ts).dt.days.astype(int)

    # Scores: recency menor = melhor → ascending=False (maior recency_dias → score 1).
    df["r_score"] = _score_by_quintile(df["recency_dias"], ascending=False)
    df["f_score"] = _score_by_quintile(df["frequency"], ascending=True)
    df["m_score"] = _score_by_quintile(df["monetary"], ascending=True)

    df["segmento"] = df.apply(_assign_segment, axis=1)

    return df[_RFM_COLUMNS]


def cohort_produto(conn: sqlite3.Connection, date_from: str, date_to: str) -> pd.DataFrame:
    """Cohort de produtos por mês de lançamento — agregado.

    "Mês de lançamento" = menor date_closed do produto **no banco inteiro**
    (não apenas na janela). Cada linha do resultado é um grupo de produtos que
    tiveram primeira venda no mesmo mês.

    Args:
        conn: conexão SQLite aberta.
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
    # 1) Mapa item_id → mês de lançamento (banco inteiro, não apenas janela).
    launch_query = """
        SELECT
            oi.item_id,
            strftime('%Y-%m', MIN(o.date_closed)) AS mes_lancamento
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        WHERE o.status = 'paid'
        GROUP BY oi.item_id
    """
    launches = pd.read_sql_query(launch_query, conn)
    if launches.empty:
        return pd.DataFrame()

    # 2) Receita por item × mês corrente na janela.
    revenue_query = """
        SELECT
            oi.item_id,
            strftime('%Y-%m', o.date_closed)              AS mes_corrente,
            ROUND(SUM(oi.quantity * oi.unit_price), 2)    AS receita
        FROM order_items oi
        JOIN orders o ON o.order_id = oi.order_id
        WHERE o.status = 'paid'
          AND o.date_closed >= ?
          AND o.date_closed <  ?
        GROUP BY oi.item_id, mes_corrente
    """
    revenue = pd.read_sql_query(revenue_query, conn, params=(date_from, date_to))
    if revenue.empty:
        return pd.DataFrame()

    # 3) Join + agregação por (mes_lancamento, mes_corrente).
    merged = revenue.merge(launches, on="item_id", how="left")
    agg = (
        merged.groupby(["mes_lancamento", "mes_corrente"], as_index=False)["receita"].sum().round(2)
    )

    # 4) Pivot para o formato triangular.
    pivot = agg.pivot(index="mes_lancamento", columns="mes_corrente", values="receita")
    pivot.index.name = "mes_lancamento"
    pivot.columns.name = "mes_corrente"

    # 5) Garantir ordenação cronológica e recorte "só janela para colunas".
    pivot = pivot.sort_index(axis=0).sort_index(axis=1)

    return pivot

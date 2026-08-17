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

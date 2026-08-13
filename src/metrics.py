"""Camada de métricas financeiras e operacionais — funções puras.

Cada função recebe conexão SQLite + janela temporal e devolve DataFrame ou
dict. Sem side effects: leitura pura, sem prints, sem HTTP, sem escrita.
"""

from __future__ import annotations

import sqlite3

import pandas as pd

# Heurística: assume COGS = 55% da receita bruta. Documentado no spec.
# Ficará configurável quando o modo real (ingestão ML) alimentar custo real.
COST_ESTIMATE_RATE = 0.55


def fluxo_financeiro(conn: sqlite3.Connection, date_from: str, date_to: str) -> pd.DataFrame:
    """DataFrame por dia com receita, custos e líquido para a janela dada.

    Args:
        conn: conexão SQLite aberta.
        date_from: início inclusivo (ISO 8601, ex: "2026-07-25").
        date_to: fim exclusivo (ISO 8601).

    Returns:
        DataFrame com colunas: date, receita_bruta, taxas_ml, frete,
        custo_estimado, liquido. Uma linha por dia com pedidos pagos.
        Vazio se nenhum pedido no range.
    """
    query = """
        SELECT
            substr(date_closed, 1, 10) AS date,
            SUM(total_amount)         AS receita_bruta,
            SUM(marketplace_fee)      AS taxas_ml,
            SUM(shipping_cost)        AS frete
        FROM orders
        WHERE status = 'paid'
          AND date_closed >= ?
          AND date_closed < ?
        GROUP BY substr(date_closed, 1, 10)
        ORDER BY date
    """
    df = pd.read_sql_query(query, conn, params=(date_from, date_to))
    df["custo_estimado"] = (df["receita_bruta"] * COST_ESTIMATE_RATE).round(2)
    df["liquido"] = (
        df["receita_bruta"] - df["taxas_ml"] - df["frete"] - df["custo_estimado"]
    ).round(2)
    return df[["date", "receita_bruta", "taxas_ml", "frete", "custo_estimado", "liquido"]]


def top_produtos(
    conn: sqlite3.Connection, date_from: str, date_to: str, n: int = 10
) -> dict[str, pd.DataFrame]:
    """Top N produtos e top N categorias por receita.

    Args:
        conn: conexão SQLite.
        date_from: início inclusivo (ISO 8601).
        date_to: fim exclusivo.
        n: número de linhas retornadas em cada ranking. Default 10.

    Returns:
        dict com chaves:
        - "produtos": DataFrame [item_id, title, category_name, unidades, receita]
        - "categorias": DataFrame [category_id, category_name, unidades, receita]
        Ambos ordenados por receita desc.
    """
    produtos = pd.read_sql_query(
        """
        SELECT
            oi.item_id                                       AS item_id,
            ic.title                                          AS title,
            cc.name                                           AS category_name,
            SUM(oi.quantity)                                  AS unidades,
            ROUND(SUM(oi.quantity * oi.unit_price), 2)        AS receita
        FROM order_items oi
        JOIN orders o        ON o.order_id     = oi.order_id
        JOIN items_cache ic  ON ic.item_id     = oi.item_id
        JOIN categories_cache cc ON cc.category_id = ic.category_id
        WHERE o.status = 'paid'
          AND o.date_closed >= ?
          AND o.date_closed <  ?
        GROUP BY oi.item_id, ic.title, cc.name
        ORDER BY receita DESC
        LIMIT ?
        """,
        conn,
        params=(date_from, date_to, n),
    )

    # Segunda query separada — não dá pra reaproveitar o LIMIT do ranking de
    # produtos aqui: filtrar por top-N produtos distorceria os totais por
    # categoria (excluiria receita de produtos fora do top-N).
    categorias = pd.read_sql_query(
        """
        SELECT
            cc.category_id                                    AS category_id,
            cc.name                                           AS category_name,
            SUM(oi.quantity)                                  AS unidades,
            ROUND(SUM(oi.quantity * oi.unit_price), 2)        AS receita
        FROM order_items oi
        JOIN orders o        ON o.order_id     = oi.order_id
        JOIN items_cache ic  ON ic.item_id     = oi.item_id
        JOIN categories_cache cc ON cc.category_id = ic.category_id
        WHERE o.status = 'paid'
          AND o.date_closed >= ?
          AND o.date_closed <  ?
        GROUP BY cc.category_id, cc.name
        ORDER BY receita DESC
        LIMIT ?
        """,
        conn,
        params=(date_from, date_to, n),
    )

    return {"produtos": produtos, "categorias": categorias}

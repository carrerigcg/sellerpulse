"""Utilitários compartilhados entre os módulos de porte pra Postgres/asyncpg.

Hoje só tem `_parse_boundary`, usada por `metrics_pg.py` e `segmentation_pg.py`
pra converter os limites de janela temporal (`date_from`/`date_to`) antes de
passar pra `pool.fetch(...)`. Vive aqui em vez de em qualquer um dos dois
módulos pra evitar duplicação ou import cruzado entre eles.
"""

from __future__ import annotations

from datetime import UTC, datetime


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

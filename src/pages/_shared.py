"""Utilitários compartilhados pelas páginas do dashboard.

Extraído de `pages/{1_executive,2_products,3_customers}.py` — cada página
antes duplicava `_DEMO_DB`, `_get_window`, o padrão de abertura read-only
do SQLite e um cálculo de janela anterior. Um lugar só facilita manutenção
(mudar TTL, migrar path do banco, ajustar fallback de janela).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

DEMO_DB = Path("data/demo.db")
_DEFAULT_WINDOW_DAYS = 90


def get_window() -> tuple[str, str]:
    """Lê o período da sidebar; fallback = últimos 90 dias.

    Precondição: `dashboard.py` já rodou (via multipage router do Streamlit)
    e escreveu `date_from`/`date_to` em `st.session_state`.
    """
    default_to = date.today()
    default_from = default_to - timedelta(days=_DEFAULT_WINDOW_DAYS)
    return (
        st.session_state.get("date_from", default_from.isoformat()),
        st.session_state.get("date_to", default_to.isoformat()),
    )


def previous_window(date_from: str, date_to: str) -> tuple[str, str]:
    """Janela imediatamente anterior, de mesma duração — pra calcular delta."""
    dt_from = date.fromisoformat(date_from)
    dt_to = date.fromisoformat(date_to)
    delta_dias = (dt_to - dt_from).days
    prev_to = dt_from
    prev_from = prev_to - timedelta(days=delta_dias)
    return prev_from.isoformat(), prev_to.isoformat()


@contextmanager
def open_ro(db_path: Path = DEMO_DB) -> Iterator[sqlite3.Connection]:
    """Abre SQLite em modo read-only (URI). Fecha automático."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        yield conn
    finally:
        conn.close()

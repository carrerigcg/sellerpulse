"""Página 1 do dashboard — Executive Summary.

Espelha visualmente o PDF: 4 KPI cards + fluxo financeiro (barras empilhadas
por dia) + comparativo semana anterior. Consome apenas metrics.* — nunca
abre SQLite direto.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.metrics import fluxo_financeiro, reputacao_devolucao

_DEMO_DB = Path("data/demo.db")


def _get_window() -> tuple[str, str]:
    """Lê período da sidebar; fallback = últimos 90 dias."""
    default_to = date.today()
    default_from = default_to - timedelta(days=90)
    return (
        st.session_state.get("date_from", default_from.isoformat()),
        st.session_state.get("date_to", default_to.isoformat()),
    )


@st.cache_data(ttl=300)
def _load_fluxo(date_from: str, date_to: str) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{_DEMO_DB}?mode=ro", uri=True)
    try:
        return fluxo_financeiro(conn, date_from, date_to)
    finally:
        conn.close()


@st.cache_data(ttl=300)
def _load_reputacao(date_from: str, date_to: str) -> dict:
    conn = sqlite3.connect(f"file:{_DEMO_DB}?mode=ro", uri=True)
    try:
        return reputacao_devolucao(conn, date_from, date_to)
    finally:
        conn.close()


def _render_kpis(fluxo: pd.DataFrame, reput: dict) -> None:
    if fluxo.empty:
        receita = custo = liquido = 0.0
    else:
        receita = float(fluxo["receita_bruta"].sum())
        custo = float((fluxo["taxas_ml"] + fluxo["frete"] + fluxo["custo_estimado"]).sum())
        liquido = float(fluxo["liquido"].sum())
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Receita bruta", f"R$ {receita:,.2f}")
    col2.metric("Custo total", f"R$ {custo:,.2f}")
    col3.metric("Lucro líquido", f"R$ {liquido:,.2f}")
    col4.metric("Nível ML", reput.get("nivel_ml", "—"))


def _render_fluxo_chart(fluxo: pd.DataFrame) -> None:
    if fluxo.empty:
        st.info("Sem pedidos pagos no período selecionado.")
        return
    tidy = fluxo.melt(
        id_vars="date",
        value_vars=["receita_bruta", "taxas_ml", "frete", "custo_estimado", "liquido"],
        var_name="componente",
        value_name="valor",
    )
    fig = px.bar(
        tidy,
        x="date",
        y="valor",
        color="componente",
        title="Fluxo financeiro por dia",
        labels={"date": "Data", "valor": "R$", "componente": "Componente"},
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_comparativo(date_from: str, date_to: str, fluxo_atual: pd.DataFrame) -> None:
    """Compara receita/custo/líquido com a janela imediatamente anterior."""
    dt_from = date.fromisoformat(date_from)
    dt_to = date.fromisoformat(date_to)
    delta_dias = (dt_to - dt_from).days
    prev_to = dt_from
    prev_from = prev_to - timedelta(days=delta_dias)
    fluxo_prev = _load_fluxo(prev_from.isoformat(), prev_to.isoformat())

    def _sum(df: pd.DataFrame, col: str) -> float:
        return float(df[col].sum()) if not df.empty else 0.0

    receita_atual = _sum(fluxo_atual, "receita_bruta")
    receita_prev = _sum(fluxo_prev, "receita_bruta")
    liquido_atual = _sum(fluxo_atual, "liquido")
    liquido_prev = _sum(fluxo_prev, "liquido")

    def _delta_pct(atual: float, prev: float) -> str:
        if prev == 0:
            return "n/a"
        return f"{100 * (atual - prev) / prev:+.1f}%"

    st.subheader("Comparativo com janela anterior")
    col1, col2 = st.columns(2)
    col1.metric(
        "Receita bruta",
        f"R$ {receita_atual:,.2f}",
        delta=_delta_pct(receita_atual, receita_prev),
    )
    col2.metric(
        "Lucro líquido",
        f"R$ {liquido_atual:,.2f}",
        delta=_delta_pct(liquido_atual, liquido_prev),
    )


def _main() -> None:
    date_from, date_to = _get_window()
    st.title("Executive Summary")
    st.caption(f"{date_from} — {date_to}")

    fluxo = _load_fluxo(date_from, date_to)
    reput = _load_reputacao(date_from, date_to)

    _render_kpis(fluxo, reput)
    st.divider()
    _render_fluxo_chart(fluxo)
    st.divider()
    _render_comparativo(date_from, date_to, fluxo)


_main()

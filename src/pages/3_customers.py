"""Página 3 do dashboard — Customer Analytics.

Métricas de compradores + scatter RFM colorido por segmento + distribuição
por segmento. Consome apenas segmentation.rfm_scores.

Nota: com dados sintéticos atuais (1 buyer por order), o dashboard pode
exibir baixa variabilidade de segmentos — comportamento esperado nesta fase.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from src.segmentation import rfm_scores

_DEMO_DB = Path("data/demo.db")


def _get_window() -> tuple[str, str]:
    default_to = date.today()
    default_from = default_to - timedelta(days=90)
    return (
        st.session_state.get("date_from", default_from.isoformat()),
        st.session_state.get("date_to", default_to.isoformat()),
    )


@st.cache_data(ttl=300)
def _load_rfm(date_from: str, date_to: str) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{_DEMO_DB}?mode=ro", uri=True)
    try:
        return rfm_scores(conn, date_from, date_to)
    finally:
        conn.close()


def _render_kpis(rfm: pd.DataFrame) -> None:
    if rfm.empty:
        total = champions = at_risk = ticket = 0
    else:
        total = int(rfm["buyer_id"].nunique())
        champions = int((rfm["segmento"] == "Champions").sum())
        at_risk = int((rfm["segmento"] == "At Risk").sum())
        ticket = float(rfm["monetary"].mean()) if total > 0 else 0.0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Compradores únicos", f"{total}")
    col2.metric("Champions", f"{champions}")
    col3.metric("At Risk", f"{at_risk}")
    col4.metric("Ticket médio", f"R$ {ticket:,.2f}")


def _render_scatter(rfm: pd.DataFrame) -> None:
    st.subheader("Distribuição RFM (Frequency × Monetary)")
    if rfm.empty:
        st.info("Sem compradores no período selecionado.")
        return
    fig = px.scatter(
        rfm,
        x="frequency",
        y="monetary",
        color="segmento",
        size="r_score",
        hover_data=["buyer_id", "recency_dias", "r_score", "f_score", "m_score"],
        labels={"frequency": "Frequência (n compras)", "monetary": "Monetary (R$)"},
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_segment_bar(rfm: pd.DataFrame) -> None:
    st.subheader("Compradores por segmento")
    if rfm.empty:
        return
    counts = rfm["segmento"].value_counts().reset_index()
    counts.columns = ["segmento", "n_compradores"]
    fig = px.bar(
        counts,
        x="n_compradores",
        y="segmento",
        orientation="h",
        labels={"n_compradores": "Compradores", "segmento": "Segmento"},
    )
    st.plotly_chart(fig, use_container_width=True)


def _main() -> None:
    date_from, date_to = _get_window()
    st.title("Customer Analytics")
    st.caption(f"{date_from} — {date_to}")

    rfm = _load_rfm(date_from, date_to)
    _render_kpis(rfm)
    st.divider()
    _render_scatter(rfm)
    st.divider()
    _render_segment_bar(rfm)


_main()

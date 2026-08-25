"""Página 3 do dashboard — Customer Analytics.

Métricas de compradores + scatter RFM colorido por segmento + distribuição
por segmento. Consome apenas segmentation.rfm_scores. Estilo vem de src.theme.

Nota: com dados sintéticos atuais (1 buyer por order), o dashboard pode
exibir baixa variabilidade de segmentos — comportamento esperado nesta fase.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import plotly.express as px
import streamlit as st

from src import theme
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
        total = champions = at_risk = 0
        ticket = 0.0
    else:
        total = int(rfm["buyer_id"].nunique())
        champions = int((rfm["segmento"] == "Champions").sum())
        at_risk = int((rfm["segmento"] == "At Risk").sum())
        ticket = float(rfm["monetary"].mean()) if total > 0 else 0.0

    theme.kpi_row(
        [
            theme.Kpi("Compradores únicos", f"{total}", "users"),
            theme.Kpi("Champions", f"{champions}", "star"),
            theme.Kpi("At Risk", f"{at_risk}", "alert"),
            theme.Kpi("Ticket médio", f"R$ {ticket:,.2f}", "ticket"),
        ]
    )


def _render_scatter(rfm: pd.DataFrame) -> None:
    with theme.card("Distribuição RFM", "frequência × valor, colorido por segmento"):
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
            labels={
                "frequency": "Frequência (n compras)",
                "monetary": "Monetary (R$)",
                "segmento": "",
            },
            color_discrete_sequence=theme.CHART_SEQUENCE,
        )
        st.plotly_chart(theme.style_fig(fig), width="stretch")


def _render_segment_bar(rfm: pd.DataFrame) -> None:
    with theme.card("Compradores por segmento"):
        if rfm.empty:
            st.info("Sem compradores no período.")
            return
        counts = rfm["segmento"].value_counts().reset_index()
        counts.columns = ["segmento", "n_compradores"]
        fig = px.bar(
            counts,
            x="n_compradores",
            y="segmento",
            orientation="h",
            labels={"n_compradores": "Compradores", "segmento": ""},
            color_discrete_sequence=[theme.COLORS["accent"]],
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(theme.style_fig(fig), width="stretch")


def _main() -> None:
    theme.inject_css()
    date_from, date_to = _get_window()
    theme.page_header(
        "Customer Analytics",
        "Quem compra, com que frequência e quanto vale cada segmento.",
        f"{date_from} — {date_to}",
    )

    rfm = _load_rfm(date_from, date_to)
    _render_kpis(rfm)

    col_scatter, col_barra = st.columns([2, 1])
    with col_scatter:
        _render_scatter(rfm)
    with col_barra:
        _render_segment_bar(rfm)


_main()

"""Página 2 do dashboard — Product Analytics.

Top produtos/categorias + curva Pareto ABC + heatmap de cohort por mês
de lançamento. Consome metrics.top_produtos, segmentation.abc_pareto,
segmentation.cohort_produto.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.metrics import top_produtos
from src.segmentation import abc_pareto, cohort_produto

_DEMO_DB = Path("data/demo.db")


def _get_window() -> tuple[str, str]:
    default_to = date.today()
    default_from = default_to - timedelta(days=90)
    return (
        st.session_state.get("date_from", default_from.isoformat()),
        st.session_state.get("date_to", default_to.isoformat()),
    )


@st.cache_data(ttl=300)
def _load_top(date_from: str, date_to: str, n: int = 10) -> dict[str, pd.DataFrame]:
    conn = sqlite3.connect(f"file:{_DEMO_DB}?mode=ro", uri=True)
    try:
        return top_produtos(conn, date_from, date_to, n=n)
    finally:
        conn.close()


@st.cache_data(ttl=300)
def _load_abc(date_from: str, date_to: str) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{_DEMO_DB}?mode=ro", uri=True)
    try:
        return abc_pareto(conn, date_from, date_to)
    finally:
        conn.close()


@st.cache_data(ttl=300)
def _load_cohort(date_from: str, date_to: str) -> pd.DataFrame:
    conn = sqlite3.connect(f"file:{_DEMO_DB}?mode=ro", uri=True)
    try:
        return cohort_produto(conn, date_from, date_to)
    finally:
        conn.close()


def _render_top(top: dict[str, pd.DataFrame]) -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top 10 produtos")
        st.dataframe(top["produtos"], use_container_width=True, hide_index=True)
    with col2:
        st.subheader("Top 10 categorias")
        st.dataframe(top["categorias"], use_container_width=True, hide_index=True)


def _render_pareto(abc: pd.DataFrame) -> None:
    st.subheader("Curva Pareto ABC")
    if abc.empty:
        st.info("Sem dados no período.")
        return
    fig = go.Figure()
    fig.add_trace(go.Bar(x=abc["sku"], y=abc["receita"], name="Receita", marker_color="#1f77b4"))
    fig.add_trace(
        go.Scatter(
            x=abc["sku"],
            y=abc["receita_acumulada_pct"],
            name="% acumulado",
            yaxis="y2",
            mode="lines+markers",
            line={"color": "#ff7f0e"},
        )
    )
    fig.update_layout(
        yaxis={"title": "Receita (R$)"},
        yaxis2={"title": "% acumulado", "overlaying": "y", "side": "right", "range": [0, 105]},
        xaxis={"title": "SKU"},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    st.plotly_chart(fig, use_container_width=True)
    contagem = abc["classe"].value_counts().to_dict()
    st.caption(
        f"Classe A: {contagem.get('A', 0)} produtos · "
        f"Classe B: {contagem.get('B', 0)} · "
        f"Classe C: {contagem.get('C', 0)}"
    )


def _render_cohort(cohort: pd.DataFrame) -> None:
    st.subheader("Cohort por mês de lançamento — receita")
    if cohort.empty:
        st.info("Sem dados suficientes para cohort no período.")
        return
    fig = px.imshow(
        cohort,
        labels={"x": "Mês corrente", "y": "Mês de lançamento", "color": "Receita (R$)"},
        aspect="auto",
        color_continuous_scale="Blues",
    )
    st.plotly_chart(fig, use_container_width=True)


def _main() -> None:
    date_from, date_to = _get_window()
    st.title("Product Analytics")
    st.caption(f"{date_from} — {date_to}")

    top = _load_top(date_from, date_to, n=10)
    _render_top(top)
    st.divider()

    abc = _load_abc(date_from, date_to)
    _render_pareto(abc)
    st.divider()

    cohort = _load_cohort(date_from, date_to)
    _render_cohort(cohort)


_main()

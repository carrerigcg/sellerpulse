"""Página 2 do dashboard — Product Analytics.

Top produtos/categorias + curva Pareto ABC + heatmap de cohort por mês
de lançamento. Consome metrics.top_produtos, segmentation.abc_pareto,
segmentation.cohort_produto. Todo o estilo vem de src.theme.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import theme
from src.dashboard_helpers import get_active_conn, get_window, is_session_conn, source_key
from src.metrics import top_produtos
from src.segmentation import abc_pareto, cohort_produto

_COLS_PRODUTOS = {
    "item_id": st.column_config.TextColumn("SKU", width="small"),
    "title": st.column_config.TextColumn("Produto", width="medium"),
    "category_name": st.column_config.TextColumn("Categoria"),
    "unidades": st.column_config.NumberColumn("Unid.", format="%d"),
    "receita": st.column_config.NumberColumn("Receita", format="R$ %.2f"),
}
# category_id = None esconde a coluna: é chave técnica, não interessa na tela.
_COLS_CATEGORIAS = {
    "category_id": None,
    "category_name": st.column_config.TextColumn("Categoria", width="medium"),
    "unidades": st.column_config.NumberColumn("Unid.", format="%d"),
    "receita": st.column_config.NumberColumn("Receita", format="R$ %.2f"),
}


@st.cache_data(ttl=300)
def _load_top(date_from: str, date_to: str, source: str, n: int = 10) -> dict[str, pd.DataFrame]:
    conn = get_active_conn()
    try:
        return top_produtos(conn, date_from, date_to, n=n)
    finally:
        if not is_session_conn(conn):
            conn.close()


@st.cache_data(ttl=300)
def _load_abc(date_from: str, date_to: str, source: str) -> pd.DataFrame:
    conn = get_active_conn()
    try:
        return abc_pareto(conn, date_from, date_to)
    finally:
        if not is_session_conn(conn):
            conn.close()


@st.cache_data(ttl=300)
def _load_cohort(date_from: str, date_to: str, source: str) -> pd.DataFrame:
    conn = get_active_conn()
    try:
        return cohort_produto(conn, date_from, date_to)
    finally:
        if not is_session_conn(conn):
            conn.close()


def _render_top(top: dict[str, pd.DataFrame]) -> None:
    col1, col2 = st.columns(2)
    with col1, theme.card("Top 10 produtos", "por receita no período"):
        st.dataframe(
            top["produtos"],
            column_config=_COLS_PRODUTOS,
            width="stretch",
            hide_index=True,
        )
    with col2, theme.card("Top 10 categorias", "por receita no período"):
        st.dataframe(
            top["categorias"],
            column_config=_COLS_CATEGORIAS,
            width="stretch",
            hide_index=True,
        )


def _render_pareto(abc: pd.DataFrame) -> None:
    with theme.card("Curva Pareto ABC", "receita por SKU e acumulado"):
        if abc.empty:
            st.info("Sem dados no período.")
            return
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=abc["sku"],
                y=abc["receita"],
                name="Receita",
                marker_color=theme.COLORS["accent"],
            )
        )
        fig.add_trace(
            go.Scatter(
                x=abc["sku"],
                y=abc["receita_acumulada_pct"],
                name="% acumulado",
                yaxis="y2",
                mode="lines+markers",
                line={"color": theme.COLORS["gold"]},
                marker={"color": theme.COLORS["gold"], "size": 5},
            )
        )
        theme.style_fig(fig)
        # Eixo secundário é específico deste gráfico — fica local, não no theme.
        fig.update_layout(
            yaxis={"title": "Receita (R$)"},
            yaxis2={
                "title": "% acumulado",
                "overlaying": "y",
                "side": "right",
                "range": [0, 105],
                "gridcolor": "rgba(0,0,0,0)",
            },
            xaxis={"title": ""},
        )
        st.plotly_chart(fig, width="stretch")
        contagem = abc["classe"].value_counts().to_dict()
        st.caption(
            f"Classe A: {contagem.get('A', 0)} produtos · "
            f"Classe B: {contagem.get('B', 0)} · "
            f"Classe C: {contagem.get('C', 0)}"
        )


def _render_cohort(cohort: pd.DataFrame) -> None:
    with theme.card("Cohort por mês de lançamento", "receita acumulada por mês corrente"):
        if cohort.empty:
            st.info("Sem dados suficientes para cohort no período.")
            return
        fig = px.imshow(
            cohort,
            labels={"x": "Mês corrente", "y": "Mês de lançamento", "color": "Receita (R$)"},
            aspect="auto",
            color_continuous_scale=theme.CHART_CONTINUOUS,
        )
        st.plotly_chart(theme.style_fig(fig), width="stretch")


def _main() -> None:
    theme.inject_css()
    date_from, date_to = get_window()
    theme.page_header(
        "Product Analytics",
        "Concentração de receita por produto, categoria e safra de lançamento.",
        f"{date_from} — {date_to}",
    )

    top = _load_top(date_from, date_to, source_key(), n=10)
    _render_top(top)
    st.divider()

    abc = _load_abc(date_from, date_to, source_key())
    _render_pareto(abc)
    st.divider()

    cohort = _load_cohort(date_from, date_to, source_key())
    _render_cohort(cohort)


_main()

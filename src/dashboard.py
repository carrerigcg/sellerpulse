"""SellerPulse dashboard — entry point Streamlit.

Rodar via `python -m src.main abrir-dashboard` (usa `streamlit run` internamente).
Multi-page é gerenciado nativamente pelo Streamlit lendo a pasta `src/pages/`.
A sidebar aqui é global — grava período em `st.session_state` para as páginas.
"""

from __future__ import annotations

from datetime import date, timedelta
from importlib import metadata

import streamlit as st

from src import theme

st.set_page_config(page_title="SellerPulse", page_icon="📊", layout="wide")


def _get_version() -> str:
    try:
        return metadata.version("sellerpulse")
    except metadata.PackageNotFoundError:
        return "dev"


def _render_sidebar() -> None:
    st.sidebar.markdown(
        '<div class="sp-brand">'
        '<div class="sp-brand__name">Seller<em>Pulse</em></div>'
        f'<div class="sp-brand__version">v{_get_version()}</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    default_to = date.today()
    default_from = default_to - timedelta(days=90)
    with st.sidebar.container(border=True):
        st.markdown(
            '<div class="sp-card__head"><span class="sp-card__title">Período</span></div>',
            unsafe_allow_html=True,
        )
        date_from = st.date_input("Início", value=default_from, key="sidebar_date_from")
        date_to = st.date_input("Fim", value=default_to, key="sidebar_date_to")
    st.session_state["date_from"] = date_from.isoformat()
    st.session_state["date_to"] = date_to.isoformat()

    # Guard roda ANTES da instanciação do widget — Streamlit >= 1.29 proíbe
    # escrever em st.session_state[key] após o widget com aquele key ter sido
    # criado no mesmo run.
    if st.session_state.get("sidebar_modo", "").startswith("Real"):
        st.session_state["sidebar_modo"] = "Demo"
        st.sidebar.warning("Modo Real chega na v0.4.0 — voltando para Demo.")

    with st.sidebar.container(border=True):
        st.markdown(
            '<div class="sp-card__head"><span class="sp-card__title">Fonte de dados</span></div>',
            unsafe_allow_html=True,
        )
        st.radio(
            "Modo",
            options=["Demo", "Real (v0.4.0)"],
            index=0,
            captions=[
                "Dados sintéticos versionados",
                "OAuth Mercado Livre — em desenvolvimento (Fase 3)",
            ],
            key="sidebar_modo",
        )
        st.selectbox(
            "Categoria",
            options=["Todas"],
            index=0,
            disabled=True,
            help="Disponível na v1.0",
            key="sidebar_categoria",
        )


def _render_home() -> None:
    periodo = f"{st.session_state['date_from']} — {st.session_state['date_to']}"
    st.markdown(
        '<div class="sp-cover">'
        '<div class="sp-cover__name">Seller<em>Pulse</em></div>'
        '<p class="sp-cover__tagline">Analytics para vendedores Mercado Livre.</p>'
        f'<span class="sp-pill">{periodo}</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        theme.nav_card(
            "Executive",
            "Receita, custos e resultado do período, com variação sobre a janela anterior.",
            "revenue",
            "pages/1_executive.py",
        )
    with col2:
        theme.nav_card(
            "Products",
            "Top produtos e categorias, curva Pareto ABC e cohort por mês de lançamento.",
            "box",
            "pages/2_products.py",
        )
    with col3:
        theme.nav_card(
            "Customers",
            "Segmentação RFM dos compradores e distribuição por segmento.",
            "users",
            "pages/3_customers.py",
        )


theme.inject_css()
_render_sidebar()
_render_home()

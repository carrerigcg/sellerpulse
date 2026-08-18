"""SellerPulse dashboard — entry point Streamlit.

Rodar via `python -m src.main abrir-dashboard` (usa `streamlit run` internamente).
Multi-page é gerenciado nativamente pelo Streamlit lendo a pasta `src/pages/`.
A sidebar aqui é global — grava período em `st.session_state` para as páginas.
"""

from __future__ import annotations

from datetime import date, timedelta
from importlib import metadata

import streamlit as st

st.set_page_config(page_title="SellerPulse", page_icon="📊", layout="wide")


def _get_version() -> str:
    try:
        return metadata.version("sellerpulse")
    except metadata.PackageNotFoundError:
        return "dev"


def _render_sidebar() -> None:
    st.sidebar.title("SellerPulse")

    default_to = date.today()
    default_from = default_to - timedelta(days=90)
    date_from = st.sidebar.date_input(
        "Início", value=default_from, key="sidebar_date_from"
    )
    date_to = st.sidebar.date_input("Fim", value=default_to, key="sidebar_date_to")
    st.session_state["date_from"] = date_from.isoformat()
    st.session_state["date_to"] = date_to.isoformat()

    st.sidebar.divider()

    # Toggle Demo/Real — Real desabilitado nesta fase.
    # st.radio não desabilita opções individuais; usamos captions para sinalizar.
    modo = st.sidebar.radio(
        "Modo",
        options=["Demo", "Real"],
        index=0,
        captions=["Dados sintéticos versionados", "Configure data/business.db para habilitar"],
        key="sidebar_modo",
    )
    if modo == "Real":
        st.sidebar.warning("Modo Real não disponível nesta versão — voltando para Demo.")
        st.session_state["sidebar_modo"] = "Demo"

    st.sidebar.selectbox(
        "Categoria",
        options=["Todas"],
        index=0,
        disabled=True,
        help="Disponível na v1.0",
        key="sidebar_categoria",
    )

    st.sidebar.divider()
    st.sidebar.caption(f"SellerPulse v{_get_version()}")


_render_sidebar()

st.title("SellerPulse")
st.caption("Analytics interativo para vendedores Mercado Livre.")
st.info("Selecione uma página na barra lateral à esquerda.")

"""SellerPulse dashboard — entry point Streamlit.

Rodar via `python -m src.main abrir-dashboard` (usa `streamlit run` internamente).
Multi-page é gerenciado nativamente pelo Streamlit lendo a pasta `src/pages/`.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="SellerPulse", page_icon="📊", layout="wide")

st.title("SellerPulse")
st.caption("Analytics interativo para vendedores Mercado Livre.")
st.info("Selecione uma página na barra lateral à esquerda.")

# Sidebar global — completada na Task 6.
st.sidebar.title("SellerPulse")

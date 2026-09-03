"""Helpers de UI consumidos por src/dashboard.py e src/pages/*.py.

Único módulo (fora de dashboard.py e pages/) que importa streamlit.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from src.auth import OAuthClient, OAuthError, TokenSet
from src.ml_client import MLClient
from src.session_store import InMemoryTokenStore

_DEMO_DB = Path("data/demo.db")

_SESSION_KEYS_TO_CLEAR = (
    "ml_tokens",
    "ml_seller_id",
    "ml_nickname",
    "ml_token_store",
    "session_conn",
    "ingest_result",
    "ingest_done_at",
    "oauth_state",
    "oauth_error_message",
)


def get_config(key: str) -> str | None:
    """Lê configuração preferindo st.secrets (Streamlit Cloud) sobre env vars.

    Streamlit Cloud tem UI de secrets criptografados; localmente usamos .env
    via python-dotenv (já carregado no boot do dashboard).
    """
    try:
        value = st.secrets.get(key) if hasattr(st, "secrets") else None
    except (FileNotFoundError, KeyError, AttributeError):
        value = None
    if value:
        return value
    return os.environ.get(key)


def get_active_conn() -> sqlite3.Connection:
    """Devolve a conn ativa baseado no toggle Demo/Real.

    - Modo Demo (ou modo Real sem conta conectada): conn read-only pro demo.db.
    - Modo Real + conta conectada: session_state["session_conn"] (SQLite :memory:).

    Caller é responsável por fechar a conn do demo (a session_conn é gerenciada
    pelo próprio session_state — não fechar!). Uso típico: chamar dentro de
    função cacheada com try/finally que fecha se veio do demo.
    """
    modo = st.session_state.get("sidebar_modo", "Demo")
    session_conn = st.session_state.get("session_conn")
    if modo == "Real" and session_conn is not None:
        return session_conn
    return sqlite3.connect(f"file:{_DEMO_DB}?mode=ro", uri=True)


def is_session_conn(conn: sqlite3.Connection) -> bool:
    """True se a conn é a session_conn (não deve ser fechada pelo caller).

    Útil pras páginas fazerem try/finally sem fechar por engano a conn
    de longa vida do modo Real.
    """
    session_conn = st.session_state.get("session_conn")
    return session_conn is not None and conn is session_conn


def source_key() -> str:
    """Chave estável de cache pras pages — muda quando o toggle Demo/Real muda.

    Real inclui o ml_seller_id pra separar caches entre sellers distintos que
    caem no mesmo worker Streamlit; Demo é sempre `demo`.
    """
    modo = st.session_state.get("sidebar_modo", "Demo")
    if modo == "Real":
        return f"real:{st.session_state.get('ml_seller_id', 'none')}"
    return "demo"


def get_window() -> tuple[str, str]:
    """Lê período (date_from, date_to) da sidebar; fallback = últimos 90 dias."""
    default_to = date.today()
    default_from = default_to - timedelta(days=90)
    return (
        st.session_state.get("date_from", default_from.isoformat()),
        st.session_state.get("date_to", default_to.isoformat()),
    )


def is_ml_connected() -> bool:
    """True se há tokens ML válidos + session_conn pronta pra queries.

    Semântica única pro dashboard e pages saberem "modo Real está pronto".
    Não checa expiração de tokens (isso é responsabilidade de get_active_ml_client);
    apenas verifica que as chaves críticas estão presentes no session_state.
    """
    return "ml_tokens" in st.session_state and "session_conn" in st.session_state


def clear_ml_session_state() -> None:
    """Remove chaves de auth/ingest e volta sidebar pra Demo.

    Usado por: refresh failure (get_active_ml_client) e disconnect explícito
    (Task 6/7 do dashboard). Idempotente — seguro chamar mesmo sem sessão ativa.
    """
    for k in _SESSION_KEYS_TO_CLEAR:
        st.session_state.pop(k, None)
    st.session_state["sidebar_modo"] = "Demo"


def get_active_ml_client() -> MLClient | None:
    """Devolve MLClient com token válido (renova se necessário), ou None.

    Retorna None se não conectado. Renova tokens transparente se expirados.
    Em falha de refresh (token revogado), limpa session_state e retorna None
    — a próxima renderização vai mostrar o botão de reconectar.
    """
    tokens: TokenSet | None = st.session_state.get("ml_tokens")
    if tokens is None:
        return None

    store: InMemoryTokenStore | None = st.session_state.get("ml_token_store")
    seller_id = st.session_state.get("ml_seller_id")
    if tokens.is_expired() and store is not None and seller_id is not None:
        client_id = get_config("ML_CLIENT_ID")
        client_secret = get_config("ML_CLIENT_SECRET")
        if not client_id or not client_secret:
            return None
        oauth = OAuthClient(client_id=client_id, client_secret=client_secret, store=store)
        try:
            tokens = oauth.refresh()
            st.session_state["ml_tokens"] = tokens
        except OAuthError:
            clear_ml_session_state()
            return None

    return MLClient(access_token=tokens.access_token)

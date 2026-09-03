"""Testes de src/dashboard_helpers.py — helpers que dependem de session_state."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest

from src.auth import TokenSet
from src.session_store import InMemoryTokenStore


def test_get_config_prefers_st_secrets(monkeypatch):
    from src import dashboard_helpers

    fake_secrets = {"ML_CLIENT_ID": "from-secrets"}
    monkeypatch.setattr(dashboard_helpers.st, "secrets", fake_secrets)
    monkeypatch.setenv("ML_CLIENT_ID", "from-env")
    assert dashboard_helpers.get_config("ML_CLIENT_ID") == "from-secrets"


def test_get_config_falls_back_to_env(monkeypatch):
    from src import dashboard_helpers

    monkeypatch.setattr(dashboard_helpers.st, "secrets", {})
    monkeypatch.setenv("ML_CLIENT_ID", "from-env")
    assert dashboard_helpers.get_config("ML_CLIENT_ID") == "from-env"


def test_get_config_returns_none_when_missing(monkeypatch):
    from src import dashboard_helpers

    monkeypatch.setattr(dashboard_helpers.st, "secrets", {})
    monkeypatch.delenv("ML_CLIENT_ID", raising=False)
    assert dashboard_helpers.get_config("ML_CLIENT_ID") is None


def test_get_active_conn_returns_demo_when_modo_demo(monkeypatch, tmp_path):
    from src import dashboard_helpers

    fake_demo = tmp_path / "demo.db"
    sqlite3.connect(str(fake_demo)).close()
    monkeypatch.setattr(dashboard_helpers, "_DEMO_DB", fake_demo)
    monkeypatch.setattr(dashboard_helpers.st, "session_state", {"sidebar_modo": "Demo"})

    conn = dashboard_helpers.get_active_conn()
    assert conn is not None
    # Verifica read-only: SQLite deve rejeitar writes
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("CREATE TABLE x (a INTEGER)")
    conn.close()


def test_get_active_conn_returns_session_conn_when_modo_real_and_connected(monkeypatch):
    from src import dashboard_helpers

    session_conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(
        dashboard_helpers.st,
        "session_state",
        {
            "sidebar_modo": "Real",
            "session_conn": session_conn,
        },
    )
    conn = dashboard_helpers.get_active_conn()
    assert conn is session_conn
    session_conn.close()


def test_get_active_conn_returns_demo_when_modo_real_but_not_connected(monkeypatch, tmp_path):
    from src import dashboard_helpers

    fake_demo = tmp_path / "demo.db"
    sqlite3.connect(str(fake_demo)).close()
    monkeypatch.setattr(dashboard_helpers, "_DEMO_DB", fake_demo)
    monkeypatch.setattr(dashboard_helpers.st, "session_state", {"sidebar_modo": "Real"})
    conn = dashboard_helpers.get_active_conn()
    assert conn is not None
    conn.close()


def test_get_active_ml_client_returns_none_when_not_connected(monkeypatch):
    from src import dashboard_helpers

    monkeypatch.setattr(dashboard_helpers.st, "session_state", {})
    assert dashboard_helpers.get_active_ml_client() is None


def test_get_active_ml_client_returns_client_when_connected(monkeypatch):
    from src import dashboard_helpers
    from src.ml_client import MLClient

    tokens = TokenSet(
        access_token="APP_USR-valid",
        refresh_token="TG-valid",
        expires_at=datetime.now(UTC) + timedelta(hours=5),
    )
    store = InMemoryTokenStore()
    store.save(tokens, seller_id=999)
    monkeypatch.setattr(
        dashboard_helpers.st,
        "session_state",
        {
            "ml_tokens": tokens,
            "ml_seller_id": 999,
            "ml_token_store": store,
        },
    )
    monkeypatch.setattr(dashboard_helpers, "get_config", lambda k: "test-value")

    client = dashboard_helpers.get_active_ml_client()
    assert isinstance(client, MLClient)


# Cobertura extra para atingir gate ≥85% — branches não exercitados nos 8 testes-base.


def test_get_config_handles_secrets_raising_filenotfound(monkeypatch):
    """st.secrets levanta FileNotFoundError sem .streamlit/secrets.toml local."""
    from src import dashboard_helpers

    class RaisingSecrets:
        def get(self, key):
            raise FileNotFoundError("no secrets.toml")

    monkeypatch.setattr(dashboard_helpers.st, "secrets", RaisingSecrets())
    monkeypatch.setenv("ML_CLIENT_ID", "from-env")
    assert dashboard_helpers.get_config("ML_CLIENT_ID") == "from-env"


def test_is_session_conn_true_for_session_conn(monkeypatch):
    from src import dashboard_helpers

    session_conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(dashboard_helpers.st, "session_state", {"session_conn": session_conn})
    assert dashboard_helpers.is_session_conn(session_conn) is True
    session_conn.close()


def test_is_session_conn_false_for_other_conn(monkeypatch):
    from src import dashboard_helpers

    session_conn = sqlite3.connect(":memory:")
    other = sqlite3.connect(":memory:")
    monkeypatch.setattr(dashboard_helpers.st, "session_state", {"session_conn": session_conn})
    assert dashboard_helpers.is_session_conn(other) is False
    session_conn.close()
    other.close()


def test_is_ml_connected_true_when_tokens_and_session_conn_present(monkeypatch):
    from src import dashboard_helpers

    monkeypatch.setattr(
        dashboard_helpers.st,
        "session_state",
        {
            "ml_tokens": object(),
            "session_conn": object(),
        },
    )
    assert dashboard_helpers.is_ml_connected() is True


def test_is_ml_connected_false_when_missing_either_key(monkeypatch):
    from src import dashboard_helpers

    # Ambos ausentes
    monkeypatch.setattr(dashboard_helpers.st, "session_state", {})
    assert dashboard_helpers.is_ml_connected() is False
    # Só tokens
    monkeypatch.setattr(dashboard_helpers.st, "session_state", {"ml_tokens": object()})
    assert dashboard_helpers.is_ml_connected() is False
    # Só session_conn
    monkeypatch.setattr(dashboard_helpers.st, "session_state", {"session_conn": object()})
    assert dashboard_helpers.is_ml_connected() is False


def test_get_active_ml_client_refreshes_expired_tokens(monkeypatch):
    """Tokens expirados devem ser renovados antes de devolver o client."""
    from src import dashboard_helpers
    from src.ml_client import MLClient

    expired = TokenSet(
        access_token="APP_USR-old",
        refresh_token="TG-old",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    fresh = TokenSet(
        access_token="APP_USR-new",
        refresh_token="TG-new",
        expires_at=datetime.now(UTC) + timedelta(hours=6),
    )
    store = InMemoryTokenStore()
    store.save(expired, seller_id=42)
    state = {
        "ml_tokens": expired,
        "ml_seller_id": 42,
        "ml_token_store": store,
    }
    monkeypatch.setattr(dashboard_helpers.st, "session_state", state)
    monkeypatch.setattr(dashboard_helpers, "get_config", lambda k: "test-value")
    monkeypatch.setattr(dashboard_helpers.OAuthClient, "refresh", lambda self: fresh)

    client = dashboard_helpers.get_active_ml_client()
    assert isinstance(client, MLClient)
    assert state["ml_tokens"] is fresh


def test_get_active_ml_client_returns_none_and_clears_state_on_refresh_failure(monkeypatch):
    """Refresh 4xx (token revogado) limpa session_state e devolve None."""
    from src import dashboard_helpers
    from src.auth import OAuthError

    expired = TokenSet(
        access_token="APP_USR-old",
        refresh_token="TG-old",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    store = InMemoryTokenStore()
    store.save(expired, seller_id=7)
    session_conn = sqlite3.connect(":memory:")
    state = {
        "ml_tokens": expired,
        "ml_seller_id": 7,
        "ml_nickname": "vendedor7",
        "ml_token_store": store,
        "session_conn": session_conn,
        "ingest_result": {"orders": 10},
        "ingest_done_at": "2026-01-01",
        "oauth_state": "csrf-token-stale",
        "oauth_error_message": "erro anterior",
        "sidebar_modo": "Real",
    }
    monkeypatch.setattr(dashboard_helpers.st, "session_state", state)
    monkeypatch.setattr(dashboard_helpers, "get_config", lambda k: "test-value")

    def _raise(self):
        raise OAuthError("revoked")

    monkeypatch.setattr(dashboard_helpers.OAuthClient, "refresh", _raise)

    assert dashboard_helpers.get_active_ml_client() is None
    # session_state deve ter sido limpo e modo revertido para Demo.
    assert "ml_tokens" not in state
    assert "ml_seller_id" not in state
    assert "ml_nickname" not in state
    assert "ml_token_store" not in state
    assert "session_conn" not in state
    assert "ingest_result" not in state
    assert "ingest_done_at" not in state
    assert "oauth_state" not in state
    assert "oauth_error_message" not in state
    assert state["sidebar_modo"] == "Demo"
    session_conn.close()


def test_get_active_ml_client_returns_none_when_expired_and_missing_config(monkeypatch):
    """Sem client_id/secret no ambiente não dá pra refrescar — retorna None."""
    from src import dashboard_helpers

    expired = TokenSet(
        access_token="APP_USR-old",
        refresh_token="TG-old",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    store = InMemoryTokenStore()
    store.save(expired, seller_id=1)
    monkeypatch.setattr(
        dashboard_helpers.st,
        "session_state",
        {
            "ml_tokens": expired,
            "ml_seller_id": 1,
            "ml_token_store": store,
        },
    )
    monkeypatch.setattr(dashboard_helpers, "get_config", lambda k: None)

    assert dashboard_helpers.get_active_ml_client() is None


def test_source_key_demo_by_default(monkeypatch):
    from src import dashboard_helpers

    monkeypatch.setattr(dashboard_helpers.st, "session_state", {})
    assert dashboard_helpers.source_key() == "demo"


def test_source_key_real_uses_seller_id(monkeypatch):
    from src import dashboard_helpers

    monkeypatch.setattr(
        dashboard_helpers.st,
        "session_state",
        {"sidebar_modo": "Real", "ml_seller_id": 42},
    )
    assert dashboard_helpers.source_key() == "real:42"


def test_source_key_real_without_seller_id(monkeypatch):
    from src import dashboard_helpers

    monkeypatch.setattr(dashboard_helpers.st, "session_state", {"sidebar_modo": "Real"})
    assert dashboard_helpers.source_key() == "real:none"


def test_get_window_reads_session_state(monkeypatch):
    from src import dashboard_helpers

    monkeypatch.setattr(
        dashboard_helpers.st,
        "session_state",
        {"date_from": "2026-01-01", "date_to": "2026-01-31"},
    )
    assert dashboard_helpers.get_window() == ("2026-01-01", "2026-01-31")


def test_get_window_falls_back_to_90_days(monkeypatch):
    from src import dashboard_helpers

    monkeypatch.setattr(dashboard_helpers.st, "session_state", {})
    date_from, date_to = dashboard_helpers.get_window()
    # Fallback é uma janela de 90 dias terminando hoje.
    today = date.today()
    assert date_to == today.isoformat()
    assert date_from == (today - timedelta(days=90)).isoformat()

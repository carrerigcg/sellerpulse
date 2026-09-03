"""Testes de src/session_auth.py — helpers OAuth em contexto web."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
import responses

from src.auth import TokenSet
from src.session_auth import (
    OAuthError,
    build_authorize_url,
    exchange_code_for_tokens,
    sanitize_oauth_error,
)


def test_build_authorize_url_includes_state_and_redirect():
    url = build_authorize_url(
        client_id="APP-123",
        redirect_uri="https://sellerpulse.streamlit.app/",
        state="csrf-token-abc",
    )
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "auth.mercadolivre.com.br"
    assert parsed.path == "/authorization"
    qs = parse_qs(parsed.query)
    assert qs["response_type"] == ["code"]
    assert qs["client_id"] == ["APP-123"]
    assert qs["redirect_uri"] == ["https://sellerpulse.streamlit.app/"]
    assert qs["state"] == ["csrf-token-abc"]


@responses.activate
def test_exchange_code_for_tokens_returns_tokenset():
    responses.add(
        responses.POST,
        "https://api.mercadolibre.com/oauth/token",
        json={
            "access_token": "APP_USR-fake-access",
            "refresh_token": "TG-fake-refresh",
            "expires_in": 21600,
        },
        status=200,
    )
    tokens = exchange_code_for_tokens(
        client_id="APP-123",
        client_secret="secret",
        code="AUTH_CODE_ABC",
        redirect_uri="https://sellerpulse.streamlit.app/",
    )
    assert isinstance(tokens, TokenSet)
    assert tokens.access_token == "APP_USR-fake-access"
    assert tokens.refresh_token == "TG-fake-refresh"
    assert tokens.expires_at > datetime.now(UTC)


@responses.activate
def test_exchange_code_raises_on_ml_error():
    responses.add(
        responses.POST,
        "https://api.mercadolibre.com/oauth/token",
        json={"error": "invalid_grant", "message": "invalid code"},
        status=400,
    )
    with pytest.raises(OAuthError) as exc_info:
        exchange_code_for_tokens(
            client_id="APP-123",
            client_secret="secret",
            code="INVALID",
            redirect_uri="https://sellerpulse.streamlit.app/",
        )
    assert "400" in str(exc_info.value)


@responses.activate
def test_exchange_code_sanitizes_ml_token_in_error_message():
    """Regressão: garante que o pipeline error → sanitize continua ativo.

    Se um refactor tirar sanitize_oauth_error do path de erro, este teste
    quebra — mesmo que a mensagem original vazasse o token no log/UI.
    """
    responses.add(
        responses.POST,
        "https://api.mercadolibre.com/oauth/token",
        body="invalid client APP_USR-leaked-abc123",
        status=400,
    )
    with pytest.raises(OAuthError) as exc_info:
        exchange_code_for_tokens(
            client_id="APP-123",
            client_secret="secret",
            code="X",
            redirect_uri="https://sellerpulse.streamlit.app/",
        )
    assert "APP_USR-leaked-abc123" not in str(exc_info.value)
    assert "[REDACTED]" in str(exc_info.value)


def test_sanitize_error_message_redacts_ml_tokens():
    msg = "erro no request com APP_USR-1234567890-abcdef-987654 na chamada"
    out = sanitize_oauth_error(msg)
    assert "APP_USR-1234567890-abcdef-987654" not in out
    assert "[REDACTED]" in out
    assert "erro no request com" in out
    assert "na chamada" in out


def test_sanitize_error_message_redacts_refresh_tokens():
    msg = "expired refresh TG-abc123def456ghi789 blocked"
    out = sanitize_oauth_error(msg)
    assert "TG-abc123def456ghi789" not in out
    assert "[REDACTED]" in out


def test_sanitize_error_message_preserves_content_without_tokens():
    msg = "erro genérico sem token"
    assert sanitize_oauth_error(msg) == msg

"""Testes do módulo de OAuth/tokens."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from src.auth import TokenStore, TokenSet


def test_save_then_load_roundtrip(tmp_tokens_file):
    store = TokenStore(tmp_tokens_file)
    tokens = TokenSet(
        access_token="acc-1",
        refresh_token="ref-1",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
    )
    store.save(tokens)
    loaded = store.load()
    assert loaded.access_token == "acc-1"
    assert loaded.refresh_token == "ref-1"


def test_load_raises_when_file_missing(tmp_tokens_file):
    store = TokenStore(tmp_tokens_file)
    with pytest.raises(FileNotFoundError):
        store.load()


def test_save_persists_iso_format(tmp_tokens_file):
    store = TokenStore(tmp_tokens_file)
    tokens = TokenSet(
        access_token="a", refresh_token="r",
        expires_at=datetime(2026, 6, 12, 14, 30, tzinfo=timezone.utc),
    )
    store.save(tokens)
    data = json.loads(tmp_tokens_file.read_text(encoding="utf-8"))
    assert data["expires_at"] == "2026-06-12T14:30:00+00:00"


def test_token_set_is_expired(tmp_tokens_file):
    expired = TokenSet(
        access_token="a", refresh_token="r",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    fresh = TokenSet(
        access_token="a", refresh_token="r",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    assert expired.is_expired() is True
    assert fresh.is_expired() is False


def test_token_set_is_expired_uses_safety_margin(tmp_tokens_file):
    """Tokens próximos de expirar devem contar como expirados (margem de 10min)."""
    almost = TokenSet(
        access_token="a", refresh_token="r",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )
    assert almost.is_expired() is True


def test_save_uses_atomic_write_no_tmp_left_behind(tmp_tokens_file):
    """Save should not leave a .tmp file behind after success."""
    store = TokenStore(tmp_tokens_file)
    tokens = TokenSet(
        access_token="a", refresh_token="r",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    store.save(tokens)
    tmp_path = tmp_tokens_file.with_suffix(tmp_tokens_file.suffix + ".tmp")
    assert tmp_tokens_file.exists()
    assert not tmp_path.exists()


import responses

from src.auth import OAuthClient, get_valid_access_token

ML_OAUTH_URL = "https://api.mercadolibre.com/oauth/token"


@responses.activate
def test_refresh_rotates_tokens(tmp_tokens_file):
    responses.add(
        responses.POST, ML_OAUTH_URL,
        json={
            "access_token": "new-acc",
            "refresh_token": "new-ref",
            "expires_in": 21600,
            "token_type": "bearer",
        },
        status=200,
    )
    store = TokenStore(tmp_tokens_file)
    old = TokenSet(
        access_token="old-acc", refresh_token="old-ref",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    store.save(old)
    oauth = OAuthClient(client_id="cid", client_secret="csec", store=store)
    new_tokens = oauth.refresh()
    assert new_tokens.access_token == "new-acc"
    # Tokens persistidos
    on_disk = store.load()
    assert on_disk.refresh_token == "new-ref"


@responses.activate
def test_get_valid_access_token_returns_cached_when_fresh(tmp_tokens_file):
    store = TokenStore(tmp_tokens_file)
    store.save(TokenSet(
        access_token="cached", refresh_token="r",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    ))
    oauth = OAuthClient(client_id="c", client_secret="s", store=store)
    token = get_valid_access_token(oauth)
    assert token == "cached"
    assert len(responses.calls) == 0  # não chamou refresh


@responses.activate
def test_get_valid_access_token_refreshes_when_expired(tmp_tokens_file):
    responses.add(
        responses.POST, ML_OAUTH_URL,
        json={"access_token": "refreshed", "refresh_token": "newref",
              "expires_in": 21600},
        status=200,
    )
    store = TokenStore(tmp_tokens_file)
    store.save(TokenSet(
        access_token="old", refresh_token="oldref",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    ))
    oauth = OAuthClient(client_id="c", client_secret="s", store=store)
    token = get_valid_access_token(oauth)
    assert token == "refreshed"


@responses.activate
def test_oauth_exchange_code_persists_tokens(tmp_tokens_file):
    responses.add(
        responses.POST, ML_OAUTH_URL,
        json={"access_token": "first-acc", "refresh_token": "first-ref",
              "expires_in": 21600},
        status=200,
    )
    store = TokenStore(tmp_tokens_file)
    oauth = OAuthClient(client_id="cid", client_secret="csec", store=store)
    tokens = oauth.exchange_code(code="abc123", redirect_uri="http://localhost:8080/callback")
    assert tokens.access_token == "first-acc"
    assert store.load().refresh_token == "first-ref"

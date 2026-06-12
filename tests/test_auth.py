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

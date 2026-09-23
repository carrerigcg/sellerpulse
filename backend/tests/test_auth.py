from __future__ import annotations

import time

import jwt
import pytest
from fastapi import HTTPException

from backend.auth import decode_supabase_jwt
from backend.deps import resolve_seller_id

TEST_JWT_SECRET = "test-secret-do-supabase"


def _make_token(user_id: str, *, expired: bool = False) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "exp": now - 10 if expired else now + 3600,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def test_decode_token_valido(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    token = _make_token("11111111-1111-1111-1111-111111111111")
    claims = decode_supabase_jwt(token)
    assert claims["sub"] == "11111111-1111-1111-1111-111111111111"


def test_decode_token_expirado_levanta_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    token = _make_token("11111111-1111-1111-1111-111111111111", expired=True)
    with pytest.raises(HTTPException) as exc_info:
        decode_supabase_jwt(token)
    assert exc_info.value.status_code == 401


def test_decode_token_lixo_levanta_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with pytest.raises(HTTPException) as exc_info:
        decode_supabase_jwt("nao-e-um-jwt")
    assert exc_info.value.status_code == 401


def test_decode_token_assinado_com_outro_secret_levanta_401(monkeypatch):
    """Assinatura inválida é o caso de ataque mais óbvio — tem que dar 401."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    token = jwt.encode(
        {"sub": "x", "aud": "authenticated", "exp": int(time.time()) + 3600},
        "secret-errado",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc_info:
        decode_supabase_jwt(token)
    assert exc_info.value.status_code == 401


async def test_resolve_seller_id_encontrado(pg_pool, test_seller):
    user_id, seller_id = test_seller
    resolvido = await resolve_seller_id(pg_pool, str(user_id))
    # resolve_seller_id devolve uuid.UUID, igual a fixture (vem do asyncpg)
    assert resolvido == seller_id


async def test_resolve_seller_id_inexistente_levanta_404(pg_pool):
    with pytest.raises(HTTPException) as exc_info:
        await resolve_seller_id(pg_pool, "99999999-9999-9999-9999-999999999999")
    assert exc_info.value.status_code == 404

# backend/deps.py
"""Dependencies do FastAPI — resolução de identidade autenticada.

O isolamento entre tenants do backend é feito AQUI: o seller_id nunca vem
do cliente, sempre é resolvido a partir do `sub` de um JWT já validado.
As queries analíticas filtram por esse valor.
"""
from __future__ import annotations

import uuid

import asyncpg
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth import decode_supabase_jwt
from backend.db import get_pool

_bearer = HTTPBearer()


async def resolve_seller_id(pool: asyncpg.Pool, user_id: str) -> uuid.UUID:
    """user_id (claim `sub` do JWT) -> seller_id. 404 se não houver seller.

    Não deveria acontecer em uso normal: um trigger no Supabase cria a row
    em `sellers` a cada insert em `auth.users`. É defesa contra estado
    inconsistente.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id FROM sellers WHERE user_id = $1", user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Usuário sem seller associado")
    return row["id"]


async def get_current_seller_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> uuid.UUID:
    """Dependency dos endpoints: valida o Bearer token e devolve o seller_id."""
    claims = decode_supabase_jwt(credentials.credentials)
    pool = await get_pool()
    return await resolve_seller_id(pool, claims["sub"])

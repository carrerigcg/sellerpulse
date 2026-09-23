# backend/tests/test_db.py
from __future__ import annotations

import backend.db as db

from .conftest import TEST_DATABASE_URL


async def test_get_pool_devolve_pool_funcional(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    await db.close_pool()  # estado limpo
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT 1") == 1
    await db.close_pool()


async def test_get_pool_e_singleton(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    await db.close_pool()
    primeiro = await db.get_pool()
    segundo = await db.get_pool()
    assert primeiro is segundo
    await db.close_pool()


async def test_close_pool_e_idempotente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    await db.close_pool()
    await db.close_pool()  # não deve levantar

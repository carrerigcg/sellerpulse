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


async def test_pool_fixa_timezone_em_utc(pg_pool):
    """Regressao: o Postgres local herda o fuso do SO (America/Sao_Paulo),
    o Supabase roda em UTC. Sem UTC fixo no pool, `to_char(...,'YYYY-MM-DD')`
    agrupa pedidos no dia errado e `$1::timestamptz` desloca a janela —
    receita diaria errada, divergindo entre teste e producao.
    """
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("show timezone") == "UTC"
        # borda da janela nao pode deslocar
        assert str(await conn.fetchval("select '2026-07-25'::timestamptz")).startswith(
            "2026-07-25 00:00:00"
        )
        # instante UTC tem que agrupar no dia UTC
        assert (
            await conn.fetchval(
                "select to_char(timestamptz '2026-07-25 02:00:00+00', 'YYYY-MM-DD')"
            )
            == "2026-07-25"
        )

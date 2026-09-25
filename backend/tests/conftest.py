# backend/tests/conftest.py
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sellerpulse_test"
)


@pytest.fixture
async def pg_pool():
    # server_settings espelha backend/db.py: sem UTC fixo, o Postgres local
    # (America/Sao_Paulo) daria resultados diferentes da producao (UTC).
    pool = await asyncpg.create_pool(
        TEST_DATABASE_URL, min_size=1, max_size=2, server_settings={"timezone": "UTC"}
    )
    yield pool
    await pool.close()


@pytest.fixture
async def test_seller(pg_pool):
    """Cria um auth.users + sellers de teste, devolve (user_id, seller_id).

    O DELETE no teardown cascateia pra sellers e todas as tabelas analíticas
    (FK com ON DELETE CASCADE), então cada teste começa limpo.
    """
    user_id = uuid.uuid4()
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO auth.users (id, email) VALUES ($1, $2)", user_id, "teste@sellerpulse.dev"
        )
        seller_id = await conn.fetchval(
            "INSERT INTO sellers (user_id) VALUES ($1) RETURNING id", user_id
        )
    yield user_id, seller_id
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM auth.users WHERE id = $1", user_id)


@pytest.fixture
async def outro_seller(pg_pool):
    """Segundo seller — usado pra provar isolamento entre tenants."""
    user_id = uuid.uuid4()
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO auth.users (id, email) VALUES ($1, $2)", user_id, "outro@sellerpulse.dev"
        )
        seller_id = await conn.fetchval(
            "INSERT INTO sellers (user_id) VALUES ($1) RETURNING id", user_id
        )
    yield user_id, seller_id
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM auth.users WHERE id = $1", user_id)


@pytest.fixture
async def pg_pool_fuso_nao_utc():
    """Pool com TimeZone de sessao DELIBERADAMENTE nao-UTC.

    `to_char` sobre `timestamptz` converte pro fuso da SESSAO. As queries
    analiticas usam `AT TIME ZONE 'UTC'` justamente pra nao depender disso —
    mas `pg_pool` fixa UTC, entao remover o `AT TIME ZONE` do codigo nao
    quebraria teste nenhum (verificado por mutacao). Este pool existe pra
    fechar essa cegueira: rodar a mesma query nos dois pools tem que dar o
    MESMO resultado.

    America/Sao_Paulo (UTC-3) e escolhido explicitamente em vez de herdar o
    fuso do SO pra que o teste seja deterministico em qualquer maquina —
    inclusive numa CI que rode em UTC, onde herdar tornaria o teste vazio.
    """
    pool = await asyncpg.create_pool(
        TEST_DATABASE_URL,
        min_size=1,
        max_size=2,
        server_settings={"timezone": "America/Sao_Paulo"},
    )
    yield pool
    await pool.close()

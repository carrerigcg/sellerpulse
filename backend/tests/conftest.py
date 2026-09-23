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
    pool = await asyncpg.create_pool(TEST_DATABASE_URL, min_size=1, max_size=2)
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

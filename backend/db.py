# backend/db.py
"""Pool de conexão Postgres compartilhado pela API.

Singleton por processo: o FastAPI abre no startup (lifespan em main.py) e
fecha no shutdown. Os testes controlam o ciclo manualmente via close_pool().
"""

from __future__ import annotations

import os

import asyncpg

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Devolve o pool do processo, criando na primeira chamada."""
    global _pool
    if _pool is None:
        database_url = os.environ["DATABASE_URL"]
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=5,
            # UTC fixo: o Supabase roda em UTC, mas um Postgres local herda o
            # fuso do SO (aqui, America/Sao_Paulo). Sem fixar, `to_char(...,
            # 'YYYY-MM-DD')` agruparia pedidos no dia errado e `$1::timestamptz`
            # deslocaria as bordas da janela — receita diaria silenciosamente
            # errada, divergindo entre teste e producao.
            server_settings={"timezone": "UTC"},
        )
    return _pool


async def close_pool() -> None:
    """Fecha o pool se existir. Idempotente."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

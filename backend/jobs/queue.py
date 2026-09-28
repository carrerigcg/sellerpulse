# backend/jobs/queue.py
"""Fila de sincronizacao em tabela Postgres.

Por que Postgres e nao Redis: o banco ja existe, ja tem backup, e
`FOR UPDATE SKIP LOCKED` da exatamente a semantica de fila que precisamos sem
mais um servico pra manter (e pagar). Vale ate um volume muito maior do que
este projeto vai ver.

A reclamacao de job e UMA sentenca: `UPDATE ... WHERE id = (SELECT ... FOR
UPDATE SKIP LOCKED LIMIT 1)`. Em dois passos (SELECT e depois UPDATE) dois
workers poderiam ler o mesmo candidato e ingerir em duplicata.
"""

from __future__ import annotations

import json
import uuid

import asyncpg

# Quanto tempo o worker "possui" o job antes de precisar renovar. Curto o
# bastante pra um job orfao (instancia hibernou) voltar rapido pra fila;
# longo o bastante pra caber um mes de ingestao entre heartbeats.
LEASE_SEGUNDOS = 120

MAX_TENTATIVAS = 3

# Candidatos: nunca reclamado, ou reclamado por um worker que morreu.
_CANDIDATO = """
    (status = 'queued' OR (status = 'running' AND leased_until < now()))
    AND attempts < $1
"""


async def enqueue(pool: asyncpg.Pool, seller_id: uuid.UUID, kind: str) -> int | None:
    """Enfileira um job. Devolve o id, ou None se o seller ja tem job ativo.

    O None nao e erro: e a resposta correta pra "ja tem trabalho em andamento
    pra voce". O caller decide se avisa o usuario ou ignora.
    """
    try:
        async with pool.acquire() as conn:
            return await conn.fetchval(
                "INSERT INTO sync_jobs (seller_id, kind) VALUES ($1, $2) RETURNING id",
                seller_id,
                kind,
            )
    except asyncpg.exceptions.UniqueViolationError:
        # Violou uniq_sync_job_ativo — ja existe job queued/running pro seller.
        return None


async def claim_next(pool: asyncpg.Pool) -> asyncpg.Record | None:
    """Reclama o job mais antigo elegivel, ou None se a fila esta vazia."""
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            f"""
            UPDATE sync_jobs SET
                status = 'running',
                attempts = attempts + 1,
                leased_until = now() + make_interval(secs => $2),
                started_at = coalesce(started_at, now())
            WHERE id = (
                SELECT id FROM sync_jobs
                WHERE {_CANDIDATO}
                ORDER BY created_at
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
            """,
            MAX_TENTATIVAS,
            float(LEASE_SEGUNDOS),
        )


async def heartbeat(
    pool: asyncpg.Pool, job_id: int, *, fase: str, processados: int, total: int
) -> None:
    """Renova o lease e publica progresso pro endpoint de status."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sync_jobs SET
                leased_until = now() + make_interval(secs => $2),
                fase = $3, processados = $4, total = $5
            WHERE id = $1
            """,
            job_id,
            float(LEASE_SEGUNDOS),
            fase,
            processados,
            total,
        )


async def salva_cursor(pool: asyncpg.Pool, job_id: int, cursor: dict) -> None:
    """Grava de onde retomar se este job for interrompido."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sync_jobs SET cursor = $2::jsonb WHERE id = $1", job_id, json.dumps(cursor)
        )


async def finish(pool: asyncpg.Pool, job_id: int, *, warnings: list[str]) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sync_jobs SET
                status = 'done', finished_at = now(), leased_until = null,
                warnings = $2::jsonb
            WHERE id = $1
            """,
            job_id,
            json.dumps(warnings),
        )


async def fail(pool: asyncpg.Pool, job_id: int, erro: str) -> None:
    """Registra a falha. Reenfileira se ainda houver tentativa, senao desiste."""
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE sync_jobs SET
                erro = $2,
                status = case when attempts >= $3 then 'failed' else 'queued' end,
                finished_at = case when attempts >= $3 then now() else null end,
                leased_until = null
            WHERE id = $1
            """,
            job_id,
            erro,
            MAX_TENTATIVAS,
        )


async def marca_esgotados(pool: asyncpg.Pool) -> int:
    """Mata jobs orfaos que ja esgotaram tentativas. Devolve quantos.

    Sem isso, um job assim ficaria 'running' com lease vencido para sempre — e
    como o indice parcial conta 'running' como ativa, o seller nao conseguiria
    enfileirar mais nada e ficaria travado sem explicacao.
    """
    async with pool.acquire() as conn:
        resultado = await conn.execute(
            """
            UPDATE sync_jobs SET
                status = 'failed', finished_at = now(), leased_until = null,
                erro = coalesce(erro, '') || ' (esgotou as tentativas)'
            WHERE status = 'running' AND leased_until < now() AND attempts >= $1
            """,
            MAX_TENTATIVAS,
        )
    # asyncpg devolve "UPDATE <n>".
    return int(resultado.split()[-1])

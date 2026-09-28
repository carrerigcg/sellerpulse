"""Testes da fila de sincronizacao em Postgres."""

from __future__ import annotations

import asyncio
import json

from backend.jobs import queue


async def _status(pool, job_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM sync_jobs WHERE id = $1", job_id)


async def test_enqueue_cria_job_na_fila(pg_pool, test_seller):
    _u, seller_id = test_seller
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    row = await _status(pg_pool, job_id)
    assert row["status"] == "queued"
    assert row["kind"] == "backfill"
    assert row["attempts"] == 0


async def test_enqueue_recusa_segundo_job_ativo_do_mesmo_seller(pg_pool, test_seller):
    """O indice parcial e a garantia; nao um `if` no app.

    Sem isso, clicar 5x em "Sincronizar agora" enfileiraria 5 backfills e o
    seller consumiria o rate limit do ML repetindo o mesmo trabalho.
    """
    _u, seller_id = test_seller
    primeiro = await queue.enqueue(pg_pool, seller_id, "backfill")
    segundo = await queue.enqueue(pg_pool, seller_id, "delta")
    assert primeiro is not None
    assert segundo is None


async def test_enqueue_permite_jobs_de_sellers_diferentes(pg_pool, test_seller, outro_seller):
    _ua, seller_a = test_seller
    _ub, seller_b = outro_seller
    assert await queue.enqueue(pg_pool, seller_a, "backfill") is not None
    assert await queue.enqueue(pg_pool, seller_b, "backfill") is not None


async def test_enqueue_libera_depois_do_job_terminar(pg_pool, test_seller):
    _u, seller_id = test_seller
    primeiro = await queue.enqueue(pg_pool, seller_id, "backfill")
    await queue.finish(pg_pool, primeiro, warnings=[])
    assert await queue.enqueue(pg_pool, seller_id, "delta") is not None


async def test_claim_next_marca_running_e_conta_tentativa(pg_pool, test_seller):
    _u, seller_id = test_seller
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    job = await queue.claim_next(pg_pool)
    assert job["id"] == job_id
    assert job["status"] == "running"
    assert job["attempts"] == 1
    assert job["leased_until"] is not None


async def test_claim_next_sem_fila_devolve_none(pg_pool):
    assert await queue.claim_next(pg_pool) is None


async def test_um_job_nunca_e_reclamado_duas_vezes(pg_pool, pg_pool_concorrente, test_seller):
    """Oito claims concorrentes sobre UM job: exatamente um leva.

    ATENCAO — usa `pg_pool_concorrente` (duas conexoes fisicas ja abertas), nao
    `pg_pool`. Com `min_size=1`, a segunda corrotina precisa abrir conexao nova
    e o handshake demora mais que a secao critica da primeira: as chamadas
    acabam serializadas por latencia de conexao, e o teste passaria mesmo com a
    reclamacao quebrada. Isso foi medido na Task 5, nao e teoria.

    Esta e a garantia central da fila. Uma implementacao em dois passos (SELECT
    o candidato, depois UPDATE) entregaria o mesmo job pra varios workers, e a
    ingestao rodaria em duplicata gravando o dobro das linhas.
    """
    _u, seller_id = test_seller
    await queue.enqueue(pg_pool, seller_id, "backfill")

    resultados = await asyncio.gather(*[queue.claim_next(pg_pool_concorrente) for _ in range(8)])
    vencedores = [r for r in resultados if r is not None]
    assert len(vencedores) == 1


async def test_lease_vencido_volta_pra_fila(pg_pool, test_seller):
    """A instancia hibernou no meio do job: o proximo worker repesca.

    Sem isso, um job interrompido ficaria 'running' para sempre e o seller
    nunca mais conseguiria sincronizar (o indice parcial bloquearia jobs novos).
    """
    _u, seller_id = test_seller
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    await queue.claim_next(pg_pool)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE sync_jobs SET leased_until = now() - interval '1 minute' WHERE id = $1",
            job_id,
        )
    repescado = await queue.claim_next(pg_pool)
    assert repescado is not None
    assert repescado["id"] == job_id
    assert repescado["attempts"] == 2


async def test_job_que_esgotou_tentativas_nao_e_repescado(pg_pool, test_seller):
    _u, seller_id = test_seller
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE sync_jobs SET status='running', attempts=$2, "
            "leased_until = now() - interval '1 minute' WHERE id = $1",
            job_id,
            queue.MAX_TENTATIVAS,
        )
    assert await queue.claim_next(pg_pool) is None


async def test_marca_esgotados_transforma_em_failed(pg_pool, test_seller):
    """Job que esgotou tentativas tem que virar `failed`, nao ficar zumbi.

    Enquanto ele esta 'running', o indice parcial impede o seller de enfileirar
    qualquer coisa — ele ficaria travado sem saber por que.
    """
    _u, seller_id = test_seller
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE sync_jobs SET status='running', attempts=$2, "
            "leased_until = now() - interval '1 minute' WHERE id = $1",
            job_id,
            queue.MAX_TENTATIVAS,
        )
    quantos = await queue.marca_esgotados(pg_pool)
    assert quantos == 1
    row = await _status(pg_pool, job_id)
    assert row["status"] == "failed"
    assert "tentativa" in row["erro"].lower()
    # E o seller volta a poder enfileirar.
    assert await queue.enqueue(pg_pool, seller_id, "delta") is not None


async def test_heartbeat_estende_lease_e_grava_progresso(pg_pool, test_seller):
    """Sem heartbeat, um job longo seria repescado no meio do trabalho."""
    _u, seller_id = test_seller
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    await queue.claim_next(pg_pool)

    # Encurta o lease de proposito pra provar que o heartbeat o empurra.
    async with pg_pool.acquire() as conn:
        quase_vencido = await conn.fetchval(
            "UPDATE sync_jobs SET leased_until = now() + interval '1 second' "
            "WHERE id = $1 RETURNING leased_until",
            job_id,
        )

    await queue.heartbeat(pg_pool, job_id, fase="Baixando pedidos", processados=7, total=20)

    depois = await _status(pg_pool, job_id)
    assert depois["fase"] == "Baixando pedidos"
    assert depois["processados"] == 7
    assert depois["total"] == 20
    assert depois["leased_until"] > quase_vencido, "o lease nao foi estendido"


async def test_finish_grava_warnings_e_conclui(pg_pool, test_seller):
    _u, seller_id = test_seller
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    await queue.claim_next(pg_pool)
    await queue.finish(pg_pool, job_id, warnings=["item X falhou"])
    row = await _status(pg_pool, job_id)
    assert row["status"] == "done"
    assert row["finished_at"] is not None
    assert "item X falhou" in row["warnings"]


async def test_fail_reenfileira_enquanto_houver_tentativa(pg_pool, test_seller):
    _u, seller_id = test_seller
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    await queue.claim_next(pg_pool)
    await queue.fail(pg_pool, job_id, "timeout na API do ML")
    row = await _status(pg_pool, job_id)
    assert row["status"] == "queued"
    assert row["erro"] == "timeout na API do ML"


async def test_fail_na_ultima_tentativa_marca_failed(pg_pool, test_seller):
    _u, seller_id = test_seller
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    for _ in range(queue.MAX_TENTATIVAS):
        await queue.claim_next(pg_pool)
        await queue.fail(pg_pool, job_id, "erro persistente")
    row = await _status(pg_pool, job_id)
    assert row["status"] == "failed"


async def test_salva_cursor(pg_pool, test_seller):
    _u, seller_id = test_seller
    job_id = await queue.enqueue(pg_pool, seller_id, "backfill")
    await queue.salva_cursor(pg_pool, job_id, {"ultimo_mes": "2026-05"})
    row = await _status(pg_pool, job_id)
    assert json.loads(row["cursor"])["ultimo_mes"] == "2026-05"

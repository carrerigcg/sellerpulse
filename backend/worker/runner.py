# backend/worker/runner.py
"""Worker que consome a fila de sincronizacao.

Roda in-process (task no lifespan do FastAPI) porque o plano gratuito do
Render nao oferece Background Worker. O custo disso e a hibernacao: a
instancia dorme apos ~15 min sem request e mata um job em andamento. As
defesas sao o lease (backend/jobs/queue.py) e o cursor daqui.

O modulo nao importa nada do FastAPI de proposito — ele roda igual como
`python -m backend.worker` no dia em que o worker virar processo dedicado.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from datetime import UTC, datetime, timedelta

import asyncpg

from backend.jobs import queue
from backend.ml import oauth
from backend.ml.ingest_pg import ingest_janela
from src.ml_client import MLClient
from src.session_auth import sanitize_oauth_error

_log = logging.getLogger(__name__)

# 6 janelas de 30 dias = 180 dias, a mesma janela do src/ingest.py original.
JANELAS_BACKFILL = 6
DIAS_POR_JANELA = 30

# Margem no delta: refaz um pouco do que ja foi pra absorver pedido que mudou
# exatamente na borda do ultimo sync.
MARGEM_DELTA = timedelta(hours=1)

# Fallback quando o seller nunca sincronizou mas pediu um delta.
JANELA_DELTA_PADRAO = timedelta(days=7)

INTERVALO_OCIOSO = 5.0


def janelas(
    ancora: datetime, *, quantidade: int = JANELAS_BACKFILL
) -> list[tuple[datetime, datetime]]:
    """Fatia [ancora - quantidade*30d, ancora] em janelas contiguas.

    A `ancora` e o `started_at` PERSISTIDO do job, nunca `now()`: calcular de
    `now()` deslocaria as janelas a cada retomada, e o cursor ("3 concluidas")
    passaria a apontar pra um periodo diferente — deixando furo no historico.
    """
    inicio = ancora - timedelta(days=quantidade * DIAS_POR_JANELA)
    return [
        (
            inicio + timedelta(days=i * DIAS_POR_JANELA),
            inicio + timedelta(days=(i + 1) * DIAS_POR_JANELA),
        )
        for i in range(quantidade)
    ]


async def _contexto_do_seller(pool: asyncpg.Pool, seller_id) -> tuple[int, datetime | None]:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT ml_seller_id, last_synced_at FROM sellers WHERE id = $1", seller_id
        )
    if row is None or row["ml_seller_id"] is None:
        raise RuntimeError(f"seller {seller_id} sem conta do Mercado Livre conectada")
    return int(row["ml_seller_id"]), row["last_synced_at"]


async def _cliente_do_seller(pool: asyncpg.Pool, seller_id) -> MLClient:
    """MLClient com token garantidamente valido (renova sob lock se preciso)."""
    return MLClient(await oauth.garante_token_valido(pool, seller_id))


async def executa_job(pool: asyncpg.Pool, job: asyncpg.Record, *, client=None) -> None:
    """Executa um job reclamado. `client` e injetado nos testes.

    Levanta em caso de falha — quem chama (o loop) registra via queue.fail,
    que decide entre reenfileirar e desistir.
    """
    seller_id = job["seller_id"]
    ml_seller_id, last_synced_at = await _contexto_do_seller(pool, seller_id)

    if client is None:
        client = await _cliente_do_seller(pool, seller_id)

    if job["kind"] == "backfill":
        await _backfill(pool, job, client, ml_seller_id, seller_id)
    else:
        await _delta(pool, job, client, ml_seller_id, seller_id, last_synced_at)


async def _backfill(pool, job, client, ml_seller_id, seller_id) -> None:
    todas = janelas(job["started_at"])
    feitas = 0
    if job["cursor"]:
        cursor = job["cursor"] if isinstance(job["cursor"], dict) else json.loads(job["cursor"])
        feitas = int(cursor.get("janelas_concluidas", 0))

    avisos: list[str] = []
    for indice in range(feitas, len(todas)):
        de, ate = todas[indice]
        await queue.heartbeat(
            pool,
            job["id"],
            fase=f"Baixando {de.date()} a {ate.date()}",
            processados=indice,
            total=len(todas),
        )
        resultado = await ingest_janela(
            pool,
            seller_id,
            client=client,
            ml_seller_id=ml_seller_id,
            date_from=de,
            date_to=ate,
            # Claims so na ultima janela: o endpoint do ML nao e paginado por
            # mes, entao pedir em cada uma traria os mesmos dados 6x.
            incluir_claims=(indice == len(todas) - 1),
        )
        avisos.extend(resultado.warnings)
        # Grava o progresso SO depois da janela inteira ter sido ingerida: se
        # ela estourar no meio, a retomada refaz essa janela (o upsert e
        # idempotente) em vez de pular dado.
        await queue.salva_cursor(pool, job["id"], {"janelas_concluidas": indice + 1})

    await _conclui(pool, job, seller_id, avisos, len(todas))


async def _delta(pool, job, client, ml_seller_id, seller_id, last_synced_at) -> None:
    agora = datetime.now(UTC)
    desde = (last_synced_at - MARGEM_DELTA) if last_synced_at else (agora - JANELA_DELTA_PADRAO)

    await queue.heartbeat(pool, job["id"], fase="Buscando atualizacoes", processados=0, total=1)
    resultado = await ingest_janela(
        pool,
        seller_id,
        client=client,
        ml_seller_id=ml_seller_id,
        date_from=desde,
        date_to=agora,
        # Sem isto, venda cancelada depois da janela original nunca voltaria.
        campo_data="date_last_updated",
        incluir_claims=True,
    )
    await _conclui(pool, job, seller_id, resultado.warnings, 1)


async def _conclui(pool, job, seller_id, avisos: list[str], total: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET last_synced_at = now() WHERE id = $1", seller_id)
    await queue.heartbeat(pool, job["id"], fase="Concluido", processados=total, total=total)
    await queue.finish(pool, job["id"], warnings=avisos)


async def loop(pool: asyncpg.Pool, *, parar: asyncio.Event, client_factory=None) -> None:
    """Consome a fila ate `parar` ser sinalizado.

    `client_factory` existe pros testes injetarem um MLClient de mentira sem
    precisar de token nem de rede.
    """
    while not parar.is_set():
        try:
            await queue.marca_esgotados(pool)
            job = await queue.claim_next(pool)
        except Exception as exc:  # noqa: BLE001 — o loop nao pode morrer
            _log.warning("[worker] falha ao acessar a fila: %s", exc)
            job = None

        if job is None:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(parar.wait(), timeout=INTERVALO_OCIOSO)
            continue

        try:
            cliente = client_factory(job) if client_factory is not None else None
            await executa_job(pool, job, client=cliente)
        except Exception as exc:  # noqa: BLE001 — boundary do job
            # sanitize_oauth_error: a mensagem vai pro banco e pro endpoint de
            # status, entao nao pode carregar token.
            try:
                await queue.fail(pool, job["id"], sanitize_oauth_error(str(exc))[:500])
            except Exception:  # noqa: BLE001
                # Se registrar a falha tambem falhar, o loop NAO pode morrer: ele
                # e a unica coisa que consome a fila, e ninguem o reinicia. O job
                # fica com lease vencido e volta a ser candidato na proxima
                # rodada; perder a mensagem de erro e barato comparado a parar
                # de sincronizar todo mundo em silencio ate o proximo deploy.
                _log.exception("[worker] falha ao registrar erro do job %s", job["id"])


def worker_habilitado() -> bool:
    """Desligavel por env. Os testes de router desligam pra nao drenar a fila."""
    return os.environ.get("WORKER_IN_PROCESS", "1") != "0"

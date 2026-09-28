# backend/routers/ml.py
"""Endpoints de conexao com o Mercado Livre.

O callback e um endpoint SEM autenticacao por Bearer — o browser chega aqui
vindo do ML, e o cookie de sessao do Supabase vive no dominio da Vercel, nao
neste. Quem prova a identidade e o `state` assinado emitido no /connect/start.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import UTC, datetime, timedelta

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from backend.db import get_pool
from backend.deps import get_current_seller_id
from backend.jobs import queue
from backend.ml import oauth
from backend.ml.tokens import PostgresTokenStore
from src.ml_client import MLClient
from src.session_auth import OAuthError, exchange_code_for_tokens, sanitize_oauth_error

router = APIRouter(prefix="/ml", tags=["ml"])

_log = logging.getLogger(__name__)


def _destino(caminho: str) -> str:
    return f"{os.environ['FRONTEND_URL'].rstrip('/')}{caminho}"


@router.post("/connect/start")
async def connect_start(seller_id: uuid.UUID = Depends(get_current_seller_id)) -> dict[str, str]:
    url, _state = oauth.url_de_consentimento(str(seller_id))
    return {"url": url}


@router.get("/callback")
async def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    # O usuario clicou em "Cancelar" na tela do ML.
    if error or not code:
        return RedirectResponse(_destino("/dashboard/conectar?erro=recusado"))

    try:
        seller_id = uuid.UUID(oauth.valida_state(state or ""))
    except (oauth.StateInvalido, ValueError):
        return RedirectResponse(_destino("/dashboard/conectar?erro=state"))

    # `requests` e sincrono: sem to_thread, estas duas chamadas travariam o
    # event loop que atende todo o resto da API.
    try:
        tokens = await asyncio.to_thread(
            exchange_code_for_tokens,
            client_id=os.environ["ML_CLIENT_ID"],
            client_secret=os.environ["ML_CLIENT_SECRET"],
            code=code,
            redirect_uri=os.environ["ML_REDIRECT_URI"],
        )
    except OAuthError:
        return RedirectResponse(_destino("/dashboard/conectar?erro=troca"))

    try:
        cliente = MLClient(tokens.access_token)
        eu = await asyncio.to_thread(cliente.get, "/users/me")
    except Exception as exc:  # noqa: BLE001 — boundary de rede
        # sanitize_oauth_error evita que um access_token acabe no log. O tipo da
        # excecao vai junto porque e o que distingue "ML fora do ar" de
        # "client_id errado" pra quem le o log do Render.
        _log.warning(
            "[ml:callback] falha em /users/me: %s: %s",
            type(exc).__name__,
            sanitize_oauth_error(str(exc)),
        )
        return RedirectResponse(_destino("/dashboard/conectar?erro=perfil"))

    ml_seller_id = int(eu["id"])
    pool = await get_pool()

    async with pool.acquire() as conn:
        dono = await conn.fetchval(
            "SELECT id FROM sellers WHERE ml_seller_id = $1 AND id <> $2",
            ml_seller_id,
            seller_id,
        )
        if dono is not None:
            return RedirectResponse(_destino("/dashboard/conectar?erro=ja-conectada"))

        try:
            await conn.execute(
                "UPDATE sellers SET ml_seller_id = $2, ml_nickname = $3 WHERE id = $1",
                seller_id,
                ml_seller_id,
                eu.get("nickname"),
            )
        except asyncpg.exceptions.UniqueViolationError:
            # Dois callbacks pra mesma conta do ML no mesmo instante: os dois
            # passam pelo SELECT acima antes de qualquer um gravar. Quem decide
            # e a constraint uniq_ml_seller_id; o SELECT continua ali so pra dar
            # a mensagem certa no caso comum, sem gastar um write que vai falhar.
            return RedirectResponse(_destino("/dashboard/conectar?erro=ja-conectada"))

    await PostgresTokenStore(pool, seller_id).save(tokens)
    await queue.enqueue(pool, seller_id, "backfill")
    return RedirectResponse(_destino("/dashboard/conectar?conectado=1"))


@router.delete("/connection", status_code=204)
async def disconnect(seller_id: uuid.UUID = Depends(get_current_seller_id)) -> None:
    """Apaga os tokens e para a sincronizacao. Os dados ingeridos ficam.

    Eles saem junto com a conta, que tem ON DELETE CASCADE desde a Sprint 1 —
    apagar historico aqui seria destruir dado que o usuario nao pediu pra
    destruir, so porque ele desplugou a integracao.
    """
    pool = await get_pool()
    await PostgresTokenStore(pool, seller_id).delete()


# Abaixo disso, um login nao dispara sincronizacao: o dado esta fresco o
# bastante e cada sync gasta rate limit da API do ML.
LIMIAR_DELTA = timedelta(hours=6)

_MOTIVOS = frozenset({"manual", "login"})


@router.post("/sync")
async def sync(
    motivo: str = "manual",
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> dict:
    """Enfileira um delta. QUEM DECIDE SE VALE A PENA E O SERVIDOR.

    `motivo=login` respeita a janela de 6h; `motivo=manual` e ordem direta do
    usuario e sempre enfileira. Deixar essa regra no frontend permitiria que
    uma aba velha, ou um cliente adulterado, a ignorasse.
    """
    if motivo not in _MOTIVOS:
        raise HTTPException(status_code=400, detail=f"motivo invalido: {motivo!r}")

    pool = await get_pool()
    async with pool.acquire() as conn:
        seller = await conn.fetchrow(
            "SELECT ml_seller_id, last_synced_at FROM sellers WHERE id = $1", seller_id
        )
    if seller is None or seller["ml_seller_id"] is None:
        raise HTTPException(
            status_code=409, detail="Conecte uma conta do Mercado Livre antes de sincronizar"
        )

    if motivo == "login":
        ultimo = seller["last_synced_at"]
        if ultimo is not None and datetime.now(UTC) - ultimo < LIMIAR_DELTA:
            return {"enfileirado": False, "motivo": "recente"}

    # Seller que nunca sincronizou precisa de HISTORICO, nao de delta: `_delta`
    # cai numa janela de 7 dias quando last_synced_at e nulo, e o seller ficaria
    # preso nela pra sempre se o backfill do callback tivesse falhado em
    # definitivo. A decisao e aqui porque so aqui se sabe o estado do seller.
    kind = "delta" if seller["last_synced_at"] is not None else "backfill"
    job_id = await queue.enqueue(pool, seller_id, kind)
    if job_id is None:
        return {"enfileirado": False, "motivo": "ja-em-andamento"}
    return {"enfileirado": True, "job_id": job_id}


@router.get("/sync/status")
async def sync_status(seller_id: uuid.UUID = Depends(get_current_seller_id)) -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        seller = await conn.fetchrow(
            "SELECT ml_seller_id, ml_nickname, last_synced_at FROM sellers WHERE id = $1",
            seller_id,
        )
        job = await conn.fetchrow(
            """
            SELECT id, kind, status, fase, processados, total, erro, warnings,
                   created_at, finished_at
            FROM sync_jobs WHERE seller_id = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            seller_id,
        )
        historico_completo = await conn.fetchval(
            "SELECT exists(SELECT 1 FROM sync_jobs WHERE seller_id = $1 "
            "AND kind = 'backfill' AND status = 'done')",
            seller_id,
        )

    return {
        "conectado": seller is not None and seller["ml_seller_id"] is not None,
        "apelido": seller["ml_nickname"] if seller else None,
        "ultima_sincronizacao": (
            seller["last_synced_at"].isoformat() if seller and seller["last_synced_at"] else None
        ),
        "job": None
        if job is None
        else {
            "id": job["id"],
            "kind": job["kind"],
            "status": job["status"],
            "fase": job["fase"],
            "processados": job["processados"],
            "total": job["total"],
            "erro": job["erro"],
            "warnings": json.loads(job["warnings"]) if job["warnings"] else [],
            "criado_em": job["created_at"].isoformat(),
            "concluido_em": job["finished_at"].isoformat() if job["finished_at"] else None,
        },
        # Responde "os numeros do dashboard cobrem os 6 meses?". Sem isso, um
        # backfill que falhou em definitivo some assim que qualquer delta
        # posterior conclui — e a tela diz "sincronizado" sobre historico
        # incompleto, sem nada indicando.
        "historico_completo": bool(historico_completo),
    }

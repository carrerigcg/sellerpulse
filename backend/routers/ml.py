# backend/routers/ml.py
"""Endpoints de conexao com o Mercado Livre.

O callback e um endpoint SEM autenticacao por Bearer — o browser chega aqui
vindo do ML, e o cookie de sessao do Supabase vive no dominio da Vercel, nao
neste. Quem prova a identidade e o `state` assinado emitido no /connect/start.
"""

from __future__ import annotations

import asyncio
import os
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse

from backend.db import get_pool
from backend.deps import get_current_seller_id
from backend.jobs import queue
from backend.ml import oauth
from backend.ml.tokens import PostgresTokenStore
from src.ml_client import MLClient
from src.session_auth import OAuthError, exchange_code_for_tokens, sanitize_oauth_error

router = APIRouter(prefix="/ml", tags=["ml"])


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
        # sanitize_oauth_error evita que um access_token acabe no log.
        print(f"[ml:callback] falha em /users/me: {sanitize_oauth_error(str(exc))}")
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

        await conn.execute(
            "UPDATE sellers SET ml_seller_id = $2, ml_nickname = $3 WHERE id = $1",
            seller_id,
            ml_seller_id,
            eu.get("nickname"),
        )

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

# backend/routers/pagamentos.py
"""O webhook do Asaas.

Chamado pelo Asaas, não por usuário: a autenticação é o token configurado no
webhook (header `asaas-access-token`), e não o JWT dos outros endpoints. O que
cada evento faz mora em `backend/pagamentos/eventos.py`.
"""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import APIRouter, Header, HTTPException, Request

from backend.db import get_pool
from backend.pagamentos import eventos

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/pagamentos", tags=["pagamentos"])

SEGREDO_DO_WEBHOOK = "ASAAS_WEBHOOK_TOKEN"


@router.post("/webhook")
async def webhook(
    request: Request,
    asaas_access_token: str | None = Header(default=None),
) -> dict:
    """Responde 200 a tudo que autenticou, inclusive ao evento ignorado.

    Para o Asaas, qualquer código que não seja 200 é falha (até 201 e 204), e
    depois de 15 falhas seguidas ele PAUSA a fila: um evento estranho não pode
    atrasar o pagamento de todos os outros vendedores. O que não se aplicou
    vira aviso no log, com o id do evento para reprocessar.

    FALHA FECHADA sem o segredo configurado, pelo mesmo motivo do
    `sync-todos`: uma variável esquecida não pode virar um endpoint aberto que
    liga plano de quem não pagou.
    """
    esperado = os.environ.get(SEGREDO_DO_WEBHOOK)
    if not esperado:
        raise HTTPException(status_code=503, detail="webhook de pagamento nao configurado")
    if asaas_access_token is None or not secrets.compare_digest(asaas_access_token, esperado):
        raise HTTPException(status_code=401, detail="token invalido")

    evento = await request.json()
    resultado = await eventos.processa(await get_pool(), evento)
    _log.info("[asaas] %s %s -> %s", evento.get("event"), evento.get("id"), resultado)
    return {"resultado": resultado}

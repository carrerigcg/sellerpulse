# backend/routers/conta.py
"""O que o vendedor pode acessar, e o aceite dos Termos de Uso.

`GET /conta/acesso` é o que o layout do painel pergunta antes de desenhar
qualquer tela: sem plano vai para /planos, sem aceite para /aceite, e com os
dois desenha o painel com os cadeados do plano. Responde sem exigir plano,
porque é justamente quem não tem que precisa saber disso.

Desenho em docs/specs/2026-10-28-planos-e-acesso-design.md.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.db import get_pool
from backend.deps import get_current_seller_id, le_plano_e_aceite, recusa
from backend.planos import VERSAO_DOS_TERMOS

router = APIRouter(prefix="/conta", tags=["conta"])

# Teto do que se grava do navegador. O valor vem do cliente e vai para o banco
# como prova; não tem por que aceitar um texto de tamanho arbitrário.
_MAX_USER_AGENT = 512
_MAX_IP = 256


@router.get("/acesso")
async def get_acesso_da_conta(seller_id: uuid.UUID = Depends(get_current_seller_id)) -> dict:
    pool = await get_pool()
    plano, aceitou = await le_plano_e_aceite(pool, seller_id)
    return {
        "plano": plano.nome if plano else None,
        "recursos": sorted(plano.recursos) if plano else [],
        "dias_de_historico": plano.dias_de_historico if plano else None,
        "produtos_na_abc": plano.produtos_na_abc if plano else None,
        "termos": {"versao": VERSAO_DOS_TERMOS, "aceito": aceitou},
    }


class Aceite(BaseModel):
    # O front manda a versão que MOSTROU. Se ela não for a vigente (aba aberta
    # antes de os termos mudarem), o aceite é recusado: aceitar um texto que
    # não é o que vale não prova nada.
    versao: str


def _ip_de(request: Request) -> str | None:
    # No Render a requisição chega por proxy, e o socket é o do proxy. Guarda
    # a cadeia inteira do X-Forwarded-For, e não só o primeiro: o primeiro
    # pode ter vindo do próprio cliente, e para prova vale mais a cadeia
    # completa do que um palpite sobre qual elo é o verdadeiro.
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado[:_MAX_IP]
    return request.client.host if request.client else None


@router.post("/aceite", status_code=201)
async def post_aceite(
    corpo: Aceite,
    request: Request,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> dict:
    pool = await get_pool()
    plano, _ = await le_plano_e_aceite(pool, seller_id)
    # Sem plano não há contrato para aceitar (decisão 1 da spec).
    if plano is None:
        raise recusa(402, "sem-plano", "Contrate um plano antes de aceitar os termos")
    if corpo.versao != VERSAO_DOS_TERMOS:
        raise recusa(409, "versao-desatualizada", "Os termos mudaram; recarregue a página")
    user_agent = (request.headers.get("user-agent") or "")[:_MAX_USER_AGENT] or None
    async with pool.acquire() as conn:
        # Aceitar de novo a mesma versão não duplica a prova: vale o primeiro.
        await conn.execute(
            """
            INSERT INTO aceites_de_termos (seller_id, versao, ip, user_agent)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (seller_id, versao) DO NOTHING
            """,
            seller_id,
            VERSAO_DOS_TERMOS,
            _ip_de(request),
            user_agent,
        )
    return {"versao": VERSAO_DOS_TERMOS, "aceito": True}

# backend/routers/demo.py
"""Endpoints publicos do seller de demonstracao.

Esta e a UNICA porta do sistema sem autenticacao. Ela existe porque a demo e
canal de aquisicao: recrutador avalia o produto e prospect ve o sistema
funcionando sem criar conta. Tres travas, todas por construcao:

1. So GET. Nenhum verbo de escrita registrado.
2. O seller_id vem de variavel de ambiente no servidor. NUNCA de parametro —
   aceitar do cliente transformaria esta porta em leitura arbitraria do
   faturamento de qualquer vendedor cadastrado.
3. Cache-Control publico. A resposta e identica pra todo mundo, entao cachear
   e de graca e protege o free tier de abuso e de cold start.
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, HTTPException, Response

from backend.analytics.metrics_pg import fluxo_financeiro, top_produtos
from backend.db import get_pool
from backend.routers._common import validate_n, validate_window

router = APIRouter(prefix="/demo", tags=["demo"])

# 5 minutos: a base de demo e estatica, mas um TTL curto evita que uma
# correcao no dado semeado demore pra aparecer.
_CACHE = "public, max-age=300"


def _seller_de_demo() -> uuid.UUID:
    """Le DEMO_SELLER_ID a cada request, nao no import.

    Lido no import, o modulo quebraria o boot da API inteira num ambiente que
    nao tem demo configurada — o resto do produto nao depende dela.
    """
    valor = os.environ.get("DEMO_SELLER_ID")
    if not valor:
        raise HTTPException(status_code=503, detail="Demonstracao nao configurada")
    try:
        return uuid.UUID(valor)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="DEMO_SELLER_ID invalido") from exc


@router.get("/fluxo-financeiro")
async def demo_fluxo_financeiro(date_from: str, date_to: str, response: Response) -> list[dict]:
    date_from, date_to = validate_window(date_from, date_to)
    response.headers["Cache-Control"] = _CACHE
    pool = await get_pool()
    df = await fluxo_financeiro(pool, _seller_de_demo(), date_from, date_to)
    return df.to_dict(orient="records")


@router.get("/top-produtos")
async def demo_top_produtos(
    date_from: str, date_to: str, response: Response, n: int = 10
) -> dict[str, list[dict]]:
    date_from, date_to = validate_window(date_from, date_to)
    n = validate_n(n)
    response.headers["Cache-Control"] = _CACHE
    pool = await get_pool()
    resultado = await top_produtos(pool, _seller_de_demo(), date_from, date_to, n)
    return {
        "produtos": resultado["produtos"].to_dict(orient="records"),
        "categorias": resultado["categorias"].to_dict(orient="records"),
    }

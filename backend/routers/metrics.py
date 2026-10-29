# backend/routers/metrics.py
"""Endpoints REST de métricas financeiras — expõe `backend/analytics/metrics_pg.py`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from backend.analytics.metrics_pg import cancelamentos, fluxo_financeiro, top_produtos
from backend.db import get_pool
from backend.deps import Acesso, get_acesso
from backend.routers._common import (
    limita_ao_historico,
    marca_historico_cortado,
    validate_n,
    validate_window,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/fluxo-financeiro")
async def get_fluxo_financeiro(
    date_from: str,
    date_to: str,
    response: Response,
    acesso: Acesso = Depends(get_acesso),
) -> list[dict]:
    date_from, date_to = validate_window(date_from, date_to)
    date_from, date_to, cortado = limita_ao_historico(acesso.plano, date_from, date_to)
    marca_historico_cortado(response, cortado)
    pool = await get_pool()
    df = await fluxo_financeiro(pool, acesso.seller_id, date_from, date_to)
    return df.to_dict(orient="records")


@router.get("/cancelamentos")
async def get_cancelamentos(
    date_from: str,
    date_to: str,
    response: Response,
    acesso: Acesso = Depends(get_acesso),
) -> dict:
    date_from, date_to = validate_window(date_from, date_to)
    date_from, date_to, cortado = limita_ao_historico(acesso.plano, date_from, date_to)
    marca_historico_cortado(response, cortado)
    pool = await get_pool()
    return await cancelamentos(pool, acesso.seller_id, date_from, date_to)


@router.get("/top-produtos")
async def get_top_produtos(
    date_from: str,
    date_to: str,
    response: Response,
    n: int = 10,
    acesso: Acesso = Depends(get_acesso),
) -> dict[str, list[dict]]:
    date_from, date_to = validate_window(date_from, date_to)
    date_from, date_to, cortado = limita_ao_historico(acesso.plano, date_from, date_to)
    marca_historico_cortado(response, cortado)
    n = validate_n(n)
    pool = await get_pool()
    resultado = await top_produtos(pool, acesso.seller_id, date_from, date_to, n)
    return {
        "produtos": resultado["produtos"].to_dict(orient="records"),
        "categorias": resultado["categorias"].to_dict(orient="records"),
    }

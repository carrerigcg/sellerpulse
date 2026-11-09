# backend/routers/metrics.py
"""Endpoints REST de métricas financeiras — expõe `backend/analytics/metrics_pg.py`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from backend.analytics.alertas_pg import alertas
from backend.analytics.custos_pg import hoje_do_vendedor
from backend.analytics.metrics_pg import cancelamentos, fluxo_financeiro, top_produtos
from backend.db import get_pool
from backend.deps import Acesso, exige, get_acesso_somavel
from backend.planos import Recurso
from backend.routers._common import (
    limita_ao_historico,
    marca_historico_cortado,
    validate_n,
    validate_window,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])

# Todas as rotas daqui são leituras que somam as contas na visão somada do
# Premium (spec 2026-11-06-premium-varias-contas, parte B).
_EXIGE_ALERTAS = exige(Recurso.ALERTAS, somavel=True)


@router.get("/fluxo-financeiro")
async def get_fluxo_financeiro(
    date_from: str,
    date_to: str,
    response: Response,
    acesso: Acesso = Depends(get_acesso_somavel),
) -> list[dict]:
    date_from, date_to = validate_window(date_from, date_to)
    date_from, date_to, cortado = limita_ao_historico(acesso.plano, date_from, date_to)
    marca_historico_cortado(response, cortado)
    pool = await get_pool()
    df = await fluxo_financeiro(pool, acesso.contas, date_from, date_to)
    return df.to_dict(orient="records")


@router.get("/cancelamentos")
async def get_cancelamentos(
    date_from: str,
    date_to: str,
    response: Response,
    acesso: Acesso = Depends(get_acesso_somavel),
) -> dict:
    date_from, date_to = validate_window(date_from, date_to)
    date_from, date_to, cortado = limita_ao_historico(acesso.plano, date_from, date_to)
    marca_historico_cortado(response, cortado)
    pool = await get_pool()
    return await cancelamentos(pool, acesso.contas, date_from, date_to)


@router.get("/top-produtos")
async def get_top_produtos(
    date_from: str,
    date_to: str,
    response: Response,
    n: int = 10,
    acesso: Acesso = Depends(get_acesso_somavel),
) -> dict[str, list[dict]]:
    date_from, date_to = validate_window(date_from, date_to)
    date_from, date_to, cortado = limita_ao_historico(acesso.plano, date_from, date_to)
    marca_historico_cortado(response, cortado)
    n = validate_n(n)
    pool = await get_pool()
    resultado = await top_produtos(pool, acesso.contas, date_from, date_to, n)
    return {
        "produtos": resultado["produtos"].to_dict(orient="records"),
        "categorias": resultado["categorias"].to_dict(orient="records"),
    }


@router.get("/alertas")
async def get_alertas(acesso: Acesso = Depends(_EXIGE_ALERTAS)) -> dict:
    # Sem janela na query: as duas regras têm janela própria (30 e 120 dias),
    # e as duas cabem no histórico de quem tem o recurso.
    pool = await get_pool()
    return await alertas(pool, acesso.contas, hoje=hoje_do_vendedor())

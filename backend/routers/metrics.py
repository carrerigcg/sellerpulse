# backend/routers/metrics.py
"""Endpoints REST de métricas financeiras — expõe `backend/analytics/metrics_pg.py`."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from backend.analytics.metrics_pg import fluxo_financeiro, top_produtos
from backend.db import get_pool
from backend.deps import get_current_seller_id
from backend.routers._common import validate_n, validate_window

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/fluxo-financeiro")
async def get_fluxo_financeiro(
    date_from: str,
    date_to: str,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> list[dict]:
    date_from, date_to = validate_window(date_from, date_to)
    pool = await get_pool()
    df = await fluxo_financeiro(pool, seller_id, date_from, date_to)
    return df.to_dict(orient="records")


@router.get("/top-produtos")
async def get_top_produtos(
    date_from: str,
    date_to: str,
    n: int = 10,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> dict[str, list[dict]]:
    date_from, date_to = validate_window(date_from, date_to)
    n = validate_n(n)
    pool = await get_pool()
    resultado = await top_produtos(pool, seller_id, date_from, date_to, n)
    return {
        "produtos": resultado["produtos"].to_dict(orient="records"),
        "categorias": resultado["categorias"].to_dict(orient="records"),
    }

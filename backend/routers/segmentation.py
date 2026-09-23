# backend/routers/segmentation.py
"""Endpoints REST de segmentação — expõe `backend/analytics/segmentation_pg.py`."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from backend.analytics.segmentation_pg import abc_pareto, cohort_produto, rfm_scores
from backend.db import get_pool
from backend.deps import get_current_seller_id
from backend.routers._common import validate_window

router = APIRouter(prefix="/segmentation", tags=["segmentation"])


@router.get("/abc")
async def get_abc(
    date_from: str,
    date_to: str,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> list[dict]:
    date_from, date_to = validate_window(date_from, date_to)
    pool = await get_pool()
    df = await abc_pareto(pool, seller_id, date_from, date_to)
    return df.to_dict(orient="records")


@router.get("/rfm")
async def get_rfm(
    date_from: str,
    date_to: str,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> list[dict]:
    date_from, date_to = validate_window(date_from, date_to)
    pool = await get_pool()
    df = await rfm_scores(pool, seller_id, date_from, date_to)
    return df.to_dict(orient="records")


@router.get("/cohort")
async def get_cohort(
    date_from: str,
    date_to: str,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> list[dict]:
    date_from, date_to = validate_window(date_from, date_to)
    pool = await get_pool()
    df = await cohort_produto(pool, seller_id, date_from, date_to)
    # Caso vazio: cohort_produto devolve um pd.DataFrame() puro (sem index
    # nomeado) -- reset_index() nele geraria uma coluna "index" espúria em
    # vez de estourar, mas o formato correto pro cliente é lista vazia.
    if df.empty:
        return []
    return df.reset_index().to_dict(orient="records")

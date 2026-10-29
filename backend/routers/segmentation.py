# backend/routers/segmentation.py
"""Endpoints REST de segmentação — expõe `backend/analytics/segmentation_pg.py`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from backend.analytics.segmentation_pg import abc_pareto, cohort_produto, rfm_scores
from backend.db import get_pool
from backend.deps import Acesso, exige, get_acesso
from backend.planos import Recurso
from backend.routers._common import limita_ao_historico, marca_historico_cortado, validate_window

router = APIRouter(prefix="/segmentation", tags=["segmentation"])

# Colunas que só existem para o desempenho dos anúncios. No plano que não o
# libera, saem da resposta: o que o plano não cobre não sai do servidor.
_COLUNAS_DE_VISITA = ("unidades_com_visita", "visitas", "conversao")

# Quantos produtos da curva ficaram de fora do plano. A tela desenha o resto
# desfocado com esse número, sem receber os produtos.
CABECALHO_PRODUTOS_OCULTOS = "X-Produtos-Ocultos"

_EXIGE_CLIENTES = exige(Recurso.CLIENTES)
_EXIGE_COHORT = exige(Recurso.COHORT)


@router.get("/abc")
async def get_abc(
    date_from: str,
    date_to: str,
    response: Response,
    acesso: Acesso = Depends(get_acesso),
) -> list[dict]:
    date_from, date_to = validate_window(date_from, date_to)
    date_from, date_to, cortado = limita_ao_historico(acesso.plano, date_from, date_to)
    marca_historico_cortado(response, cortado)
    pool = await get_pool()
    df = await abc_pareto(pool, acesso.seller_id, date_from, date_to)
    # A classe, o percentual e o acumulado são calculados sobre a curva
    # INTEIRA antes do corte: o 10º produto continua sendo "A" ou "B" de
    # verdade, e não reclassificado como se a loja tivesse só dez.
    if not acesso.plano.libera(Recurso.DESEMPENHO_ANUNCIOS):
        df = df.drop(columns=list(_COLUNAS_DE_VISITA))
    limite = acesso.plano.produtos_na_abc
    if limite is not None and not acesso.plano.libera(Recurso.ABC_COMPLETA):
        response.headers[CABECALHO_PRODUTOS_OCULTOS] = str(max(len(df) - limite, 0))
        df = df.head(limite)
    return df.to_dict(orient="records")


@router.get("/rfm")
async def get_rfm(
    date_from: str,
    date_to: str,
    response: Response,
    acesso: Acesso = Depends(_EXIGE_CLIENTES),
) -> list[dict]:
    date_from, date_to = validate_window(date_from, date_to)
    date_from, date_to, cortado = limita_ao_historico(acesso.plano, date_from, date_to)
    marca_historico_cortado(response, cortado)
    pool = await get_pool()
    df = await rfm_scores(pool, acesso.seller_id, date_from, date_to)
    return df.to_dict(orient="records")


@router.get("/cohort")
async def get_cohort(
    date_from: str,
    date_to: str,
    response: Response,
    acesso: Acesso = Depends(_EXIGE_COHORT),
) -> list[dict]:
    date_from, date_to = validate_window(date_from, date_to)
    date_from, date_to, cortado = limita_ao_historico(acesso.plano, date_from, date_to)
    marca_historico_cortado(response, cortado)
    pool = await get_pool()
    df = await cohort_produto(pool, acesso.seller_id, date_from, date_to)
    # Caso vazio: cohort_produto devolve um pd.DataFrame() puro (sem index
    # nomeado) -- reset_index() nele geraria uma coluna "index" espúria em
    # vez de estourar, mas o formato correto pro cliente é lista vazia.
    if df.empty:
        return []
    return df.reset_index().to_dict(orient="records")

# backend/routers/custos.py
"""Endpoints do custo de produto informado pelo vendedor.

PRIMEIRO ENDPOINT DE ESCRITA DE DADO DO VENDEDOR NO SISTEMA. Até aqui, tudo
que entrava no banco vinha da ingestão do Mercado Livre; aqui quem escreve é
o cliente, pela rede. Daí as três travas abaixo, que não existiam antes:

1. `seller_id` vem SEMPRE de `get_current_seller_id` (JWT validado), nunca do
   corpo nem da query. Não há parâmetro para sobrescrevê-lo — não é que ele
   seja ignorado, é que não existe.
2. `item_id` é validado contra os itens daquele vendedor. Sem isso, um PUT
   com item_id arbitrário insere linha de chave arbitrária na tabela: escrita
   não-validada num banco multi-tenant.
3. O valor tem piso e teto. O piso é `>= 0` (também no CHECK da tabela); o
   teto existe porque um erro de digitação com zeros a mais não deve poder
   transformar a margem do mês em um número negativo gigante sem que nada
   reclame.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.analytics.custos_pg import (
    gravar_custo,
    item_e_do_vendedor,
    listar_custos,
    remover_custo,
)
from backend.db import get_pool
from backend.deps import get_current_seller_id
from backend.routers._common import validate_window

router = APIRouter(prefix="/custos", tags=["custos"])

# Teto do custo unitário. Não é uma regra de negócio — é uma trava contra
# digitação: 48,00 virando 4800000,00 por um escorregão no teclado numérico
# faria a margem do mês despencar sem que nada falhasse. Dez milhões por
# unidade está muito acima de qualquer produto vendido em marketplace e muito
# abaixo do que quebra a conta. Também é o que barra `inf`, que passaria por
# um `ge=0` sozinho.
MAX_CUSTO_UNITARIO = 10_000_000.0


class CustoInformado(BaseModel):
    """Corpo do PUT. Note o que NÃO tem: `seller_id`."""

    custo_unitario: float = Field(ge=0, le=MAX_CUSTO_UNITARIO)


@router.get("")
async def get_custos(
    date_from: str,
    date_to: str,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> list[dict]:
    """Produtos vendidos na janela, com classe ABC e o custo vigente hoje."""
    date_from, date_to = validate_window(date_from, date_to)
    pool = await get_pool()
    df = await listar_custos(pool, seller_id, date_from, date_to)
    return df.to_dict(orient="records")


async def _garante_item_do_vendedor(pool, seller_id: uuid.UUID, item_id: str) -> None:
    if not await item_e_do_vendedor(pool, seller_id, item_id):
        # 404 e não 403: dizer "existe, mas não é seu" já é vazar a existência
        # do item de outro vendedor. Para quem pergunta, ele não existe.
        raise HTTPException(status_code=404, detail="Produto não encontrado para este vendedor")


@router.put("/{item_id}")
async def put_custo(
    item_id: str,
    corpo: CustoInformado,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> dict:
    """Grava o custo com vigência a partir de hoje.

    Dois PUT no mesmo dia geram uma linha só; num dia diferente, acrescentam
    um período novo e o anterior continua valendo para o passado.
    """
    pool = await get_pool()
    await _garante_item_do_vendedor(pool, seller_id, item_id)
    vigencia = await gravar_custo(pool, seller_id, item_id, corpo.custo_unitario)
    return {
        "sku": item_id,
        "custo_unitario": corpo.custo_unitario,
        "vigente_desde": vigencia.isoformat(),
    }


@router.delete("/{item_id}")
async def delete_custo(
    item_id: str,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> dict:
    """Remove a vigência de HOJE — desfaz um erro de digitação do dia.

    Não apaga histórico: vigência de ontem continua valendo para os pedidos de
    ontem. Se não havia nada gravado hoje, devolve `removido: false` em vez de
    404 — pedir para apagar o que já não existe não é erro do cliente.
    """
    pool = await get_pool()
    await _garante_item_do_vendedor(pool, seller_id, item_id)
    removido = await remover_custo(pool, seller_id, item_id)
    return {"sku": item_id, "removido": removido}

# backend/routers/custos.py
"""Endpoints do custo de produto informado pelo vendedor.

PRIMEIRO ENDPOINT DE ESCRITA DE DADO DO VENDEDOR NO SISTEMA. Até aqui, tudo
que entrava no banco vinha da ingestão do Mercado Livre; aqui quem escreve é
o cliente, pela rede. Daí as três travas abaixo, que não existiam antes:

1. `seller_id` vem SEMPRE de `get_acesso` (JWT validado), nunca do
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

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from backend.analytics.custos_pg import (
    gravar_custo,
    item_e_do_vendedor,
    listar_custos,
    remover_custo,
)
from backend.db import get_pool
from backend.deps import Acesso, get_acesso
from backend.planos import Recurso
from backend.routers._common import limita_ao_historico, marca_historico_cortado, validate_window

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
    # Falso por padrão: um cliente antigo, que não manda o campo, continua
    # gravando "a partir de hoje", como antes. Quem liga é a opção da tela.
    retroativo: bool = False


@router.get("")
async def get_custos(
    date_from: str,
    date_to: str,
    response: Response,
    acesso: Acesso = Depends(get_acesso),
) -> list[dict]:
    """Produtos vendidos na janela, com classe ABC e o custo vigente hoje."""
    date_from, date_to = validate_window(date_from, date_to)
    date_from, date_to, cortado = limita_ao_historico(acesso.plano, date_from, date_to)
    marca_historico_cortado(response, cortado)
    pool = await get_pool()
    df = await listar_custos(pool, acesso.seller_id, date_from, date_to)
    # A lista de Custos tem todos os produtos vendidos, porque é onde o custo
    # de cada um se informa. A classe A/B/C de todos eles é a curva ABC
    # inteira, que o plano sem a ABC completa não cobre: ela sai daqui.
    if not acesso.plano.libera(Recurso.ABC_COMPLETA):
        df = df.drop(columns=["classe"])
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
    acesso: Acesso = Depends(get_acesso),
) -> dict:
    """Grava o custo com vigência a partir de hoje.

    Dois PUT no mesmo dia geram uma linha só; num dia diferente, acrescentam
    um período novo e o anterior continua valendo para o passado. Com
    `retroativo`, o valor também cobre as vendas que estão sem custo — só
    elas (ver `gravar_custo`).
    """
    seller_id = acesso.seller_id
    pool = await get_pool()
    await _garante_item_do_vendedor(pool, seller_id, item_id)
    vigencia = await gravar_custo(
        pool, seller_id, item_id, corpo.custo_unitario, retroativo=corpo.retroativo
    )
    return {
        "sku": item_id,
        "custo_unitario": corpo.custo_unitario,
        "vigente_desde": vigencia.isoformat(),
    }


@router.delete("/{item_id}")
async def delete_custo(
    item_id: str,
    acesso: Acesso = Depends(get_acesso),
) -> dict:
    """Remove a vigência de HOJE — desfaz um erro de digitação do dia.

    Não apaga histórico: vigência de ontem continua valendo para os pedidos de
    ontem. Se não havia nada gravado hoje, devolve `removido: false` em vez de
    404 — pedir para apagar o que já não existe não é erro do cliente.
    """
    seller_id = acesso.seller_id
    pool = await get_pool()
    await _garante_item_do_vendedor(pool, seller_id, item_id)
    removido = await remover_custo(pool, seller_id, item_id)
    return {"sku": item_id, "removido": removido}

"""Custo de produto informado pelo vendedor — leitura e escrita.

Separado de `segmentation_pg.py` e `metrics_pg.py` porque é outra coisa: os
dois analisam, este administra. É também o primeiro módulo do sistema em que
o vendedor ESCREVE — até aqui todo dado vinha da ingestão do Mercado Livre.

A classe A/B/C de cada produto vem de `abc_pareto`, não recalculada aqui. A
regra 80/15/5 depende da receita acumulada do catálogo inteiro, já tem teste
e já tem uma cicatriz de fronteira registrada; uma segunda implementação
divergiria da primeira no dia em que alguém mexesse numa só.
"""

from __future__ import annotations

import uuid
from datetime import date

import pandas as pd

from backend.analytics._common import FUSO_DO_VENDEDOR, _parse_boundary
from backend.analytics.segmentation_pg import abc_pareto

_COLUNAS = [
    "sku",
    "titulo",
    "classe",
    "receita",
    "unidades",
    "custo_unitario",
    "vigente_desde",
]

# Unidades vendidas na janela + o custo que vale HOJE (não o da data de cada
# pedido: esta tela edita o custo corrente). O `vigente_desde` volta junto
# porque a tela precisa dizer desde quando aquele valor vale.
_UNIDADES_E_CUSTO_QUERY = f"""
    SELECT
        oi.item_id              AS sku,
        SUM(oi.quantity)::int   AS unidades,
        pc.custo_unitario,
        pc.vigente_desde
    FROM order_items oi
    JOIN orders o
      ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
    LEFT JOIN LATERAL (
        SELECT c.custo_unitario, c.vigente_desde
          FROM product_costs c
         WHERE c.seller_id = oi.seller_id
           AND c.item_id   = oi.item_id
           AND c.vigente_desde <= (now() AT TIME ZONE '{FUSO_DO_VENDEDOR}')::date
         ORDER BY c.vigente_desde DESC
         LIMIT 1
    ) pc ON TRUE
    WHERE oi.seller_id = $1
      AND o.status = 'paid'
      AND o.date_closed >= $2::timestamptz
      AND o.date_closed <  $3::timestamptz
    GROUP BY oi.item_id, pc.custo_unitario, pc.vigente_desde
"""

# O item precisa ter sido vendido por ESTE vendedor, ou estar no cache dele.
#
# A spec dizia "validado contra items_cache". `order_items` entrou junto de
# propósito: anúncio apagado no ML some do cache (a ingestão leva 404 e nunca
# cacheia) mas continua com receita real nas análises — 11,2% da receita numa
# loja real, já medido. Validar só pelo cache impediria o vendedor de informar
# o custo justamente dos produtos que ele mais vendeu e tirou do ar.
_ITEM_E_DO_VENDEDOR_QUERY = """
    SELECT EXISTS (
        SELECT 1 FROM items_cache WHERE seller_id = $1 AND item_id = $2
        UNION ALL
        SELECT 1 FROM order_items WHERE seller_id = $1 AND item_id = $2 LIMIT 1
    )
"""

_UPSERT_CUSTO = """
    INSERT INTO product_costs (seller_id, item_id, vigente_desde, custo_unitario)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (seller_id, item_id, vigente_desde)
    DO UPDATE SET custo_unitario = excluded.custo_unitario
"""


def hoje_do_vendedor() -> date:
    """O "hoje" que vale para a vigência: o dia no fuso do vendedor.

    `date.today()` do servidor seria o dia em UTC. O Render roda em UTC, então
    entre 21h e meia-noite de Brasília o custo informado seria gravado com a
    data de amanhã — e não valeria para os pedidos daquela mesma noite, que é
    justamente o horário de pico de vendas medido nesta base.
    """
    return pd.Timestamp.now(tz=FUSO_DO_VENDEDOR).date()


async def listar_custos(pool, seller_id: uuid.UUID, date_from: str, date_to: str) -> pd.DataFrame:
    """Produtos vendidos na janela, com a classe ABC e o custo vigente hoje.

    Ordenado como `abc_pareto` ordena: receita decrescente. Isso já é "classe
    A primeiro", porque a classe sai da receita acumulada — e é a ordem em que
    preencher custo muda mais a conta.

    `custo_unitario` vem `None` para quem não tem custo informado. None é
    diferente de `0.0`, e a distinção é a feature inteira: zero é a afirmação
    "não me custa nada", ausência não afirma nada.
    """
    abc = await abc_pareto(pool, seller_id, date_from, date_to)
    if abc.empty:
        return pd.DataFrame(columns=_COLUNAS)

    rows = await pool.fetch(
        _UNIDADES_E_CUSTO_QUERY, seller_id, _parse_boundary(date_from), _parse_boundary(date_to)
    )
    extras = pd.DataFrame([dict(r) for r in rows])

    df = abc[["sku", "titulo", "classe", "receita"]].merge(extras, on="sku", how="left")
    df["unidades"] = df["unidades"].fillna(0).astype(int)
    # `object` e nao float: precisa carregar None junto de numeros, e um
    # float64 com NaN viraria `NaN` no JSON, que nao e JSON valido.
    df["custo_unitario"] = df["custo_unitario"].astype(object).where(df["custo_unitario"].notna())
    df["custo_unitario"] = df["custo_unitario"].map(lambda v: float(v) if v is not None else None)
    df["vigente_desde"] = df["vigente_desde"].map(lambda v: v.isoformat() if pd.notna(v) else None)

    return df[_COLUNAS]


async def item_e_do_vendedor(pool, seller_id: uuid.UUID, item_id: str) -> bool:
    async with pool.acquire() as conn:
        return bool(await conn.fetchval(_ITEM_E_DO_VENDEDOR_QUERY, seller_id, item_id))


async def gravar_custo(
    pool, seller_id: uuid.UUID, item_id: str, custo_unitario: float, dia: date | None = None
) -> date:
    """Grava o custo com vigência a partir de `dia` (padrão: hoje).

    Dois PUT no mesmo dia geram UMA linha — o upsert bate na chave
    (seller_id, item_id, vigente_desde). Num dia diferente, acrescenta um
    período em vez de substituir, que é o que preserva o passado.
    """
    vigencia = dia or hoje_do_vendedor()
    async with pool.acquire() as conn:
        await conn.execute(_UPSERT_CUSTO, seller_id, item_id, vigencia, custo_unitario)
    return vigencia


async def remover_custo(pool, seller_id: uuid.UUID, item_id: str, dia: date | None = None) -> bool:
    """Remove a vigência de `dia` (padrão: hoje). Devolve se removeu algo.

    Desfaz erro de digitação do dia, e só. Vigência antiga não é apagada por
    aqui: o passado não se edita por esta tela.
    """
    vigencia = dia or hoje_do_vendedor()
    async with pool.acquire() as conn:
        resultado = await conn.execute(
            "DELETE FROM product_costs WHERE seller_id=$1 AND item_id=$2 AND vigente_desde=$3",
            seller_id,
            item_id,
            vigencia,
        )
    return resultado != "DELETE 0"

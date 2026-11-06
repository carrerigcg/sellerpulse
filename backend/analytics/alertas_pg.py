"""Alertas do Premium: produto com margem negativa e anúncio parado.

Spec: docs/specs/2026-11-06-premium-alertas-no-painel-design.md. As duas
regras saem do dado da própria loja, nunca de constante de mercado, e
produto sem dado suficiente fica de fora em vez de virar alerta.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from backend.analytics._common import FUSO_DO_VENDEDOR, _parse_boundary

DIAS_DA_MARGEM = 30
DIAS_DO_RITMO = 120
# Abaixo disso, o produto não tem ritmo: dizer que parou seria chute.
MIN_DIAS_COM_VENDA = 5
VEZES_O_INTERVALO = 3
# Sem piso, um produto de venda diária viraria alerta num fim de semana fraco.
MIN_DIAS_PARADO = 7

# A taxa é do pedido e o frete é do envio. Cada item fica com a parte
# proporcional à sua receita: a taxa dentro do pedido, e o frete do carrinho
# (um envio, vários pedidos) entre os pedidos pagos daquele envio. Somar o
# frete inteiro em cada pedido do carrinho inventaria prejuízo.
#
# `custo` e `frete` ficam NULL quando não se sabem: custo não informado na
# data da venda, ou envio sem frete colhido. O HAVING tira o produto inteiro
# da conta nesse caso. Pedido sem envio tem frete zero conhecido, como no
# fluxo financeiro.
_MARGEM_POR_PRODUTO = f"""
    WITH vendas AS (
        SELECT
            oi.item_id,
            o.order_id,
            o.shipment_id,
            o.total_amount,
            o.marketplace_fee,
            oi.quantity * oi.unit_price AS receita_item,
            SUM(oi.quantity * oi.unit_price) OVER (PARTITION BY o.order_id) AS receita_pedido,
            oi.quantity * pc.custo_unitario AS custo_item
        FROM order_items oi
        JOIN orders o
          ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
        LEFT JOIN LATERAL (
            SELECT c.custo_unitario
              FROM product_costs c
             WHERE c.seller_id = oi.seller_id
               AND c.item_id   = oi.item_id
               AND c.vigente_desde <= (o.date_closed AT TIME ZONE '{FUSO_DO_VENDEDOR}')::date
             ORDER BY c.vigente_desde DESC
             LIMIT 1
        ) pc ON TRUE
        WHERE oi.seller_id = $1
          AND o.status = 'paid'
          AND o.date_closed >= $2::timestamptz
          AND o.date_closed <  $3::timestamptz
    ),
    envios AS (
        SELECT o.shipment_id, SUM(o.total_amount) AS receita_envio
          FROM orders o
         WHERE o.seller_id = $1
           AND o.status = 'paid'
           AND o.shipment_id IN (SELECT shipment_id FROM vendas WHERE shipment_id IS NOT NULL)
         GROUP BY o.shipment_id
    ),
    por_item AS (
        SELECT
            v.item_id,
            v.receita_item AS receita,
            v.marketplace_fee * v.receita_item / NULLIF(v.receita_pedido, 0) AS taxa,
            CASE
                WHEN v.shipment_id IS NULL THEN 0
                ELSE sc.custo_vendedor
                     * v.total_amount / NULLIF(e.receita_envio, 0)
                     * v.receita_item / NULLIF(v.receita_pedido, 0)
            END AS frete,
            v.custo_item AS custo
        FROM vendas v
        LEFT JOIN envios e ON e.shipment_id = v.shipment_id
        LEFT JOIN shipment_costs sc
          ON sc.seller_id = $1 AND sc.shipment_id = v.shipment_id
    )
    SELECT
        p.item_id                                       AS sku,
        COALESCE(ic.title, p.item_id)                   AS titulo,
        ROUND(SUM(p.receita), 2)                        AS receita,
        ROUND(SUM(p.receita - p.taxa - p.frete - p.custo), 2) AS margem
    FROM por_item p
    LEFT JOIN items_cache ic
      ON ic.seller_id = $1 AND ic.item_id = p.item_id
    GROUP BY p.item_id, ic.title
    HAVING bool_and(p.custo IS NOT NULL)
       AND bool_and(p.frete IS NOT NULL)
       AND bool_and(p.taxa IS NOT NULL)
    ORDER BY margem, sku
"""

# Ritmo do próprio produto: dias distintos com venda, e a mediana dos dias
# entre eles (o primeiro dia não tem anterior; `percentile_cont` ignora o
# NULL). Parado é ficar sem vender mais que `VEZES_O_INTERVALO` vezes o
# intervalo normal, com piso de `MIN_DIAS_PARADO`. `$4` é o dia de
# referência: o da última sincronização.
_PARADOS = f"""
    WITH dias AS (
        SELECT DISTINCT
            oi.item_id,
            (o.date_closed AT TIME ZONE '{FUSO_DO_VENDEDOR}')::date AS dia
        FROM order_items oi
        JOIN orders o
          ON o.seller_id = oi.seller_id AND o.order_id = oi.order_id
        WHERE oi.seller_id = $1
          AND o.status = 'paid'
          AND o.date_closed >= $2::timestamptz
          AND o.date_closed <  $3::timestamptz
    ),
    intervalos AS (
        SELECT item_id, dia, dia - lag(dia) OVER (PARTITION BY item_id ORDER BY dia) AS intervalo
          FROM dias
    ),
    ritmo AS (
        SELECT item_id,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY intervalo) AS mediana,
               max(dia) AS ultima
          FROM intervalos
         GROUP BY item_id
        HAVING count(*) >= {MIN_DIAS_COM_VENDA}
    )
    SELECT
        r.item_id                     AS sku,
        COALESCE(ic.title, r.item_id) AS titulo,
        ($4::date - r.ultima)         AS dias_sem_vender,
        r.mediana,
        r.ultima
    FROM ritmo r
    LEFT JOIN items_cache ic
      ON ic.seller_id = $1 AND ic.item_id = r.item_id
    ORDER BY ($4::date - r.ultima) / r.mediana DESC, r.item_id
"""

_DIA_DA_ULTIMA_SINCRONIZACAO = f"""
    SELECT (last_synced_at AT TIME ZONE '{FUSO_DO_VENDEDOR}')::date
      FROM sellers WHERE id = $1
"""


async def alertas(pool, seller_id: uuid.UUID, *, hoje: date) -> dict:
    """Os alertas do vendedor. `hoje` é o dia no fuso dele.

    A margem olha os 30 dias antes de hoje, a mesma janela do Resumo (hoje
    fica de fora, como lá). O parado conta os dias até a última
    sincronização, e não até hoje: com a sincronização parada, todo produto
    pareceria parado sem estar.
    """
    de = _parse_boundary((hoje - timedelta(days=DIAS_DA_MARGEM)).isoformat())
    ate = _parse_boundary(hoje.isoformat())
    avaliados = await pool.fetch(_MARGEM_POR_PRODUTO, seller_id, de, ate)

    parados: list[dict] = []
    # Quantos produtos têm ritmo para medir. Sem ele, "nenhum parado" diria
    # "está tudo vendendo" sobre produtos que nem dá para avaliar.
    com_ritmo: int | None = None
    referencia = await pool.fetchval(_DIA_DA_ULTIMA_SINCRONIZACAO, seller_id)
    if referencia is not None:
        linhas = await pool.fetch(
            _PARADOS,
            seller_id,
            _parse_boundary((referencia - timedelta(days=DIAS_DO_RITMO - 1)).isoformat()),
            _parse_boundary((referencia + timedelta(days=1)).isoformat()),
            referencia,
        )
        com_ritmo = len(linhas)
        parados = [
            {
                "sku": r["sku"],
                "titulo": r["titulo"],
                "dias_sem_vender": r["dias_sem_vender"],
                "intervalo_normal": round(r["mediana"]),
                "ultima_venda": r["ultima"].isoformat(),
            }
            for r in linhas
            if r["dias_sem_vender"] > max(VEZES_O_INTERVALO * r["mediana"], MIN_DIAS_PARADO)
        ]

    return {
        "produtos_avaliados": len(avaliados),
        "margem_negativa": [
            {
                "sku": r["sku"],
                "titulo": r["titulo"],
                "receita": float(r["receita"]),
                "margem": float(r["margem"]),
            }
            for r in avaliados
            if r["margem"] < 0
        ],
        "parados": parados,
        # None = nunca sincronizou: não há dia de referência para contar.
        "produtos_com_ritmo": com_ritmo,
        "referencia": referencia.isoformat() if referencia else None,
    }

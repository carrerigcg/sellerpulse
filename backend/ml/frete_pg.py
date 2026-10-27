"""Colheita do frete que o vendedor paga, um envio por vez.

Desenho em docs/specs/2026-10-27-frete-real-design.md. As tres regras deste
arquivo:

1. **O frete do vendedor e `Σ senders[].cost` de /shipments/{id}/costs.** Em
   10 envios reais a conta fechou sempre: gross = receiver.cost + senders.cost
   + descontos do ML. Nao ha regra por modalidade a escrever.
2. **O custo e do envio, nao do pedido.** Carrinho e um envio para varios
   pedidos; a soma por dia (em `metrics_pg.py`) conta cada envio uma vez.
3. **Payload sem `senders` nao vira zero.** Zero e "o comprador pagou tudo",
   uma afirmacao. Sem o campo nao se sabe nada, e o envio fica sem linha --
   continua em `receita_sem_frete` e e tentado de novo no proximo ciclo.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field

from src.ml_client import MLAPIError

# So envio de pedido PAGO: frete de venda cancelada nao entra em conta
# nenhuma, e busca-lo seria chamada ao ML sem resposta para a tela.
#
# Sem cursor, de proposito: a lista ja exclui o que foi gravado, entao uma
# retomada recomeca exatamente do que falta.
_ENVIOS_SEM_CUSTO = """
    SELECT DISTINCT o.shipment_id
      FROM orders o
     WHERE o.seller_id = $1
       AND o.status = 'paid'
       AND o.shipment_id IS NOT NULL
       AND NOT EXISTS (
           SELECT 1 FROM shipment_costs sc
            WHERE sc.seller_id = o.seller_id AND sc.shipment_id = o.shipment_id
       )
     ORDER BY o.shipment_id
"""

# Pedido gravado sem `shipment_id` mas com o envio no payload cru. Acontece
# com o que foi ingerido entre a migration 0012 entrar em producao e o codigo
# novo subir: a ingestao velha nao preenchia a coluna, e o fluxo leria esses
# pedidos como "sem envio" -- frete zero conhecido, a afirmacao errada. A
# colheita conserta antes de listar, e depois disso a ingestao ja grava certo.
_PREENCHE_ENVIO = """
    UPDATE orders
       SET shipment_id = (raw_json->'shipping'->>'id')::bigint
     WHERE seller_id = $1
       AND shipment_id IS NULL
       AND raw_json->'shipping'->>'id' IS NOT NULL
"""

_UPSERT_CUSTO = """
    INSERT INTO shipment_costs (seller_id, shipment_id, custo_vendedor, raw_json, colhido_em)
    VALUES ($1, $2, $3, $4::jsonb, now())
    ON CONFLICT (seller_id, shipment_id)
    DO UPDATE SET custo_vendedor = excluded.custo_vendedor,
                  raw_json       = excluded.raw_json,
                  colhido_em     = excluded.colhido_em
"""


@dataclass
class ResultadoFrete:
    envios_processados: int = 0
    envios_gravados: int = 0
    warnings: list[str] = field(default_factory=list)


def custo_do_vendedor(custos: dict) -> float:
    """`Σ senders[].cost`. Levanta `ValueError` se o payload nao trouxer o campo."""
    remetentes = custos.get("senders")
    if not isinstance(remetentes, list) or not remetentes:
        raise ValueError("payload de custos sem `senders`")
    return round(sum(float(r.get("cost") or 0) for r in remetentes), 2)


async def envios_a_colher(pool, seller_id: uuid.UUID) -> list[int]:
    async with pool.acquire() as conn:
        await conn.execute(_PREENCHE_ENVIO, seller_id)
        linhas = await conn.fetch(_ENVIOS_SEM_CUSTO, seller_id)
    return [linha["shipment_id"] for linha in linhas]


async def colhe_frete(
    pool,
    seller_id: uuid.UUID,
    *,
    client,
    on_envio=None,
) -> ResultadoFrete:
    """Busca e grava o custo de cada envio que ainda nao tem.

    `on_envio` e chamado depois de cada envio. E por ele que o job renova o
    lease: a primeira colheita da loja real sao ~1.053 chamadas.

    Falha de UM envio nao derruba a colheita: vira aviso, o envio fica sem
    linha e volta na proxima rodada.
    """
    envios = await envios_a_colher(pool, seller_id)
    resultado = ResultadoFrete()

    for envio in envios:
        try:
            custos = await asyncio.to_thread(client.get, f"/shipments/{envio}/costs")
            custo = custo_do_vendedor(custos)
        except MLAPIError as exc:
            resultado.warnings.append(f"frete do envio {envio}: HTTP {exc.status_code}")
        except ValueError as exc:
            resultado.warnings.append(f"frete do envio {envio}: {exc}")
        else:
            async with pool.acquire() as conn:
                await conn.execute(_UPSERT_CUSTO, seller_id, envio, custo, json.dumps(custos))
            resultado.envios_gravados += 1
        resultado.envios_processados += 1
        if on_envio is not None:
            await on_envio(resultado.envios_processados, len(envios))

    return resultado

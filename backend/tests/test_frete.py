"""Frete real do vendedor: colheita por envio e a conta no fluxo financeiro.

Desenho em docs/specs/2026-10-27-frete-real-design.md. Os dois modos de falha
que estes testes guardam sao silenciosos: carrinho contado varias vezes
(margem menor do que e) e frete nao colhido somado como zero (margem maior do
que e). Nenhum dos dois derruba nada.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from backend.analytics.metrics_pg import fluxo_financeiro
from backend.ml.frete_pg import colhe_frete, custo_do_vendedor
from backend.worker import runner
from src.ml_client import MLAPIError

from .test_worker import _job, _seller_conectado, ambiente  # noqa: F401

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at,
                        shipment_id)
    VALUES ($1, $2, $3, $4, $5, 0, 0, 1001, '{}'::jsonb, now(), $6)
"""


async def _pedido(
    pool, sid, order_id, envio, total=100.0, quando="2026-07-10T13:00:00+00:00", status="paid"
):
    async with pool.acquire() as conn:
        await conn.execute(
            _INSERT_ORDER, order_id, sid, datetime.fromisoformat(quando), status, total, envio
        )


def _custos(*remetentes: float) -> dict:
    """Formato real de /shipments/{id}/costs, como veio na sondagem."""
    return {
        "gross_amount": sum(remetentes),
        "receiver": {"cost": 0, "discounts": []},
        "senders": [{"cost": c, "discounts": [], "compensation": 0} for c in remetentes],
    }


class ClienteDeFrete:
    """Cliente falso. Registra o que foi pedido e devolve o que mandarem."""

    def __init__(self, por_envio: dict[int, dict] | None = None, quebra: set | None = None):
        self.por_envio = por_envio or {}
        self.quebra = quebra or set()
        self.chamadas: list[str] = []

    def get(self, caminho: str, params=None):
        self.chamadas.append(caminho)
        envio = int(caminho.split("/")[2])
        if envio in self.quebra:
            raise MLAPIError(404, "envio nao encontrado")
        return self.por_envio[envio]


async def _custos_gravados(pool, sid) -> dict[int, float]:
    async with pool.acquire() as conn:
        linhas = await conn.fetch(
            "SELECT shipment_id, custo_vendedor FROM shipment_costs WHERE seller_id = $1", sid
        )
    return {linha["shipment_id"]: float(linha["custo_vendedor"]) for linha in linhas}


# ---------- a regra ----------


def test_custo_do_vendedor_e_a_soma_dos_remetentes():
    assert custo_do_vendedor(_custos(14.89)) == pytest.approx(14.89)
    assert custo_do_vendedor(_custos(10.0, 4.5)) == pytest.approx(14.5)


def test_comprador_pagou_tudo_e_custo_zero_conhecido():
    """Zero aqui e uma afirmacao -- 'o comprador pagou o frete' -- e vale."""
    assert custo_do_vendedor(_custos(0)) == 0


def test_payload_sem_remetentes_nao_vira_zero():
    """Sem `senders` nao se sabe nada. Gravar zero afirmaria frete gratis."""
    with pytest.raises(ValueError):
        custo_do_vendedor({"gross_amount": 30.0, "receiver": {"cost": 30.0}})


# ---------- a colheita ----------


async def test_carrinho_e_uma_chamada_e_uma_linha(pg_pool, test_seller):
    """Dois pedidos no mesmo envio: o frete e um so."""
    _, sid = test_seller
    await _pedido(pg_pool, sid, 1, envio=500)
    await _pedido(pg_pool, sid, 2, envio=500)
    cliente = ClienteDeFrete({500: _custos(59.64)})

    await colhe_frete(pg_pool, sid, client=cliente)

    assert cliente.chamadas == ["/shipments/500/costs"]
    assert await _custos_gravados(pg_pool, sid) == {500: 59.64}


async def test_nao_busca_de_novo_o_que_ja_tem(pg_pool, test_seller):
    _, sid = test_seller
    await _pedido(pg_pool, sid, 1, envio=500)
    await colhe_frete(pg_pool, sid, client=ClienteDeFrete({500: _custos(10.0)}))

    segundo = ClienteDeFrete({500: _custos(10.0)})
    await colhe_frete(pg_pool, sid, client=segundo)

    assert segundo.chamadas == []


async def test_so_busca_envio_de_pedido_pago(pg_pool, test_seller):
    """Frete de venda cancelada nao entra em conta nenhuma."""
    _, sid = test_seller
    await _pedido(pg_pool, sid, 1, envio=500, status="cancelled")
    cliente = ClienteDeFrete()

    await colhe_frete(pg_pool, sid, client=cliente)

    assert cliente.chamadas == []


async def test_falha_de_um_envio_vira_aviso_e_nao_grava(pg_pool, test_seller):
    """O envio sem linha continua como ausencia e volta no proximo ciclo."""
    _, sid = test_seller
    await _pedido(pg_pool, sid, 1, envio=500)
    await _pedido(pg_pool, sid, 2, envio=501)
    cliente = ClienteDeFrete({501: _custos(8.0)}, quebra={500})

    resultado = await colhe_frete(pg_pool, sid, client=cliente)

    assert await _custos_gravados(pg_pool, sid) == {501: 8.0}
    assert resultado.warnings == ["frete do envio 500: HTTP 404"]


async def test_pedido_gravado_sem_envio_e_consertado_pelo_payload(pg_pool, test_seller):
    """Pedido ingerido pelo codigo velho depois da 0012: a coluna veio vazia,
    mas o envio esta no payload. Sem o conserto, o fluxo o leria como pedido
    sem envio -- frete zero conhecido."""
    _, sid = test_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            _INSERT_ORDER.replace("'{}'::jsonb", '\'{"shipping": {"id": 777}}\'::jsonb'),
            1,
            sid,
            datetime(2026, 7, 10, 13, tzinfo=UTC),
            "paid",
            100.0,
            None,
        )
    cliente = ClienteDeFrete({777: _custos(9.0)})

    await colhe_frete(pg_pool, sid, client=cliente)

    assert await _custos_gravados(pg_pool, sid) == {777: 9.0}
    linha = (await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")).iloc[0]
    assert linha["frete"] == pytest.approx(9.0)


async def test_colheita_isola_por_seller(pg_pool, test_seller, outro_seller):
    _, sid = test_seller
    _, outro = outro_seller
    await _pedido(pg_pool, outro, 1, envio=500)
    cliente = ClienteDeFrete()

    await colhe_frete(pg_pool, sid, client=cliente)

    assert cliente.chamadas == []


# ---------- a conta no fluxo ----------


async def _custo(pool, sid, envio, valor):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO shipment_costs (seller_id, shipment_id, custo_vendedor, raw_json) "
            "VALUES ($1, $2, $3, '{}'::jsonb)",
            sid,
            envio,
            valor,
        )


async def test_carrinho_conta_o_frete_uma_vez(pg_pool, test_seller):
    """O carrinho de 7 pedidos da loja real teria pago 7 fretes."""
    _, sid = test_seller
    for pedido in range(1, 8):
        await _pedido(pg_pool, sid, pedido, envio=500)
    await _custo(pg_pool, sid, 500, 59.64)

    linha = (await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")).iloc[0]

    assert linha["frete"] == pytest.approx(59.64)
    assert linha["margem_contribuicao"] == pytest.approx(700.0 - 59.64)


async def test_frete_entra_no_dia_do_primeiro_pedido_do_envio(pg_pool, test_seller):
    """Carrinho que atravessa a borda da janela nao conta nas duas."""
    _, sid = test_seller
    await _pedido(pg_pool, sid, 1, envio=500, quando="2026-07-31T13:00:00+00:00")
    await _pedido(pg_pool, sid, 2, envio=500, quando="2026-08-01T13:00:00+00:00")
    await _custo(pg_pool, sid, 500, 20.0)

    julho = await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")
    agosto = await fluxo_financeiro(pg_pool, sid, "2026-08-01", "2026-09-01")

    assert julho["frete"].sum() == pytest.approx(20.0)
    assert agosto["frete"].sum() == 0


async def test_envio_sem_frete_colhido_e_ausencia_nao_zero(pg_pool, test_seller):
    """A receita dele aparece em `receita_sem_frete`, que e o que impede a
    margem de parecer completa."""
    _, sid = test_seller
    await _pedido(pg_pool, sid, 1, envio=500, total=100.0)
    await _pedido(pg_pool, sid, 2, envio=501, total=40.0)
    await _custo(pg_pool, sid, 500, 15.0)

    linha = (await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")).iloc[0]

    assert linha["frete"] == pytest.approx(15.0)
    assert linha["receita_sem_frete"] == pytest.approx(40.0)


async def test_pedido_sem_envio_nao_e_frete_faltando(pg_pool, test_seller):
    """Sem envio nao ha frete a pagar: e um fato, nao uma ausencia."""
    _, sid = test_seller
    await _pedido(pg_pool, sid, 1, envio=None, total=100.0)

    linha = (await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")).iloc[0]

    assert linha["frete"] == 0
    assert linha["receita_sem_frete"] == 0


async def test_shipping_cost_do_pedido_nao_e_mais_lido(pg_pool, test_seller):
    """O campo que o ML nunca preenche nao pode voltar a ser a fonte."""
    _, sid = test_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            _INSERT_ORDER.replace("0, 0, 1001", "0, 99, 1001"),
            1,
            sid,
            datetime(2026, 7, 10, 13, tzinfo=UTC),
            "paid",
            100.0,
            None,
        )

    linha = (await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")).iloc[0]

    assert linha["frete"] == 0


async def test_frete_de_outro_seller_nao_entra(pg_pool, test_seller, outro_seller):
    """Mesmo `shipment_id` nos dois tenants: o custo e de quem e."""
    _, sid = test_seller
    _, outro = outro_seller
    await _pedido(pg_pool, sid, 1, envio=500)
    await _custo(pg_pool, outro, 500, 999.0)

    linha = (await fluxo_financeiro(pg_pool, sid, "2026-07-01", "2026-08-01")).iloc[0]

    assert linha["frete"] == 0
    assert linha["receita_sem_frete"] == pytest.approx(100.0)


# ---------- o job ----------


async def test_job_de_frete_colhe_e_nao_se_auto_encadeia(pg_pool, test_seller):
    _, sid = test_seller
    await _seller_conectado(pg_pool, sid)
    await _pedido(pg_pool, sid, 1, envio=500)

    job = await _job(pg_pool, sid, kind="frete")
    await runner.executa_job(pg_pool, job, client=ClienteDeFrete({500: _custos(12.0)}))

    assert await _custos_gravados(pg_pool, sid) == {500: 12.0}
    async with pg_pool.acquire() as conn:
        total = await conn.fetchval("SELECT count(*) FROM sync_jobs WHERE seller_id=$1", sid)
    assert total == 1


async def test_job_de_frete_nao_mexe_na_marca_de_sincronizacao(pg_pool, test_seller):
    """`last_synced_at` e a marca d'agua dos PEDIDOS -- ver `_conclui`."""
    _, sid = test_seller
    await _seller_conectado(pg_pool, sid)
    async with pg_pool.acquire() as conn:
        antes = await conn.fetchval("SELECT last_synced_at FROM sellers WHERE id=$1", sid)

    job = await _job(pg_pool, sid, kind="frete")
    await runner.executa_job(pg_pool, job, client=ClienteDeFrete())

    async with pg_pool.acquire() as conn:
        depois = await conn.fetchval("SELECT last_synced_at FROM sellers WHERE id=$1", sid)
    assert depois == antes

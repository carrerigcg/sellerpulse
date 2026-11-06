"""Alertas do Premium: margem negativa e anúncio parado.

Spec: docs/specs/2026-11-06-premium-alertas-no-painel-design.md
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from backend.analytics._common import _TZ_VENDEDOR
from backend.analytics.alertas_pg import alertas

from .conftest import da_plano
from .test_routers import _auth, _item, _order, _order_item
from .test_routers import client as _client

client = _client

HOJE = date(2026, 10, 20)


def _quando(dia: date) -> str:
    return datetime.combine(dia, time(12), tzinfo=_TZ_VENDEDOR).isoformat()


async def _venda(pool, sid, order_id, item_id, dia, receita, *, taxa=0.0, envio=None):
    await _order(pool, sid, order_id, _quando(dia), receita, taxa)
    await _order_item(pool, sid, order_id, item_id, 1, receita)
    if envio is not None:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE orders SET shipment_id = $3 WHERE seller_id = $1 AND order_id = $2",
                sid,
                order_id,
                envio,
            )


async def _frete(pool, sid, envio, custo):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO shipment_costs (seller_id, shipment_id, custo_vendedor, raw_json) "
            "VALUES ($1, $2, $3, '{}'::jsonb)",
            sid,
            envio,
            custo,
        )


async def _custo(pool, sid, item_id, custo, desde=date(2000, 1, 1)):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO product_costs (seller_id, item_id, vigente_desde, custo_unitario) "
            "VALUES ($1, $2, $3, $4)",
            sid,
            item_id,
            desde,
            custo,
        )


async def _sincronizado_em(pool, sid, dia: date):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sellers SET last_synced_at = $2 WHERE id = $1",
            sid,
            datetime.combine(dia, time(20), tzinfo=_TZ_VENDEDOR),
        )


# ---------- margem negativa ----------


async def test_margem_tira_taxa_frete_e_custo(pg_pool, test_seller):
    _u, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Fone")
    await _item(pg_pool, sid, "MLB2", "Capa")
    await _venda(pg_pool, sid, 1, "MLB1", HOJE - timedelta(days=3), 100.0, taxa=20.0, envio=501)
    await _frete(pg_pool, sid, 501, 30.0)
    await _custo(pg_pool, sid, "MLB1", 60.0)
    # Sem envio: frete zero conhecido, como no fluxo financeiro.
    await _venda(pg_pool, sid, 2, "MLB2", HOJE - timedelta(days=3), 100.0, taxa=10.0)
    await _custo(pg_pool, sid, "MLB2", 50.0)

    r = await alertas(pg_pool, sid, hoje=HOJE)

    assert r["produtos_avaliados"] == 2
    assert [(a["sku"], a["titulo"]) for a in r["margem_negativa"]] == [("MLB1", "Fone")]
    assert r["margem_negativa"][0]["margem"] == pytest.approx(-10.0)
    assert r["margem_negativa"][0]["receita"] == pytest.approx(100.0)


async def test_frete_do_carrinho_e_dividido_pela_receita_de_cada_pedido(pg_pool, test_seller):
    """Somar o frete inteiro em cada pedido do carrinho inventaria prejuízo."""
    _u, sid = test_seller
    await _venda(pg_pool, sid, 1, "MLB1", HOJE - timedelta(days=2), 100.0, envio=700)
    await _venda(pg_pool, sid, 2, "MLB2", HOJE - timedelta(days=2), 300.0, envio=700)
    await _frete(pg_pool, sid, 700, 40.0)
    await _custo(pg_pool, sid, "MLB1", 95.0)
    await _custo(pg_pool, sid, "MLB2", 260.0)

    r = await alertas(pg_pool, sid, hoje=HOJE)

    # MLB1: 100 - 10 de frete - 95 = -5. MLB2: 300 - 30 - 260 = +10.
    assert [a["sku"] for a in r["margem_negativa"]] == ["MLB1"]
    assert r["margem_negativa"][0]["margem"] == pytest.approx(-5.0)


async def test_produto_com_venda_sem_custo_nao_e_avaliado(pg_pool, test_seller):
    """O custo vale só a partir da data informada: a venda anterior fica sem custo."""
    _u, sid = test_seller
    await _venda(pg_pool, sid, 1, "MLB1", HOJE - timedelta(days=10), 100.0)
    await _venda(pg_pool, sid, 2, "MLB1", HOJE - timedelta(days=2), 100.0)
    await _custo(pg_pool, sid, "MLB1", 500.0, desde=HOJE - timedelta(days=5))

    r = await alertas(pg_pool, sid, hoje=HOJE)

    assert r["produtos_avaliados"] == 0
    assert r["margem_negativa"] == []


async def test_produto_com_frete_nao_colhido_nao_e_avaliado(pg_pool, test_seller):
    _u, sid = test_seller
    await _venda(pg_pool, sid, 1, "MLB1", HOJE - timedelta(days=2), 100.0, envio=900)
    await _custo(pg_pool, sid, "MLB1", 500.0)

    r = await alertas(pg_pool, sid, hoje=HOJE)

    assert r["produtos_avaliados"] == 0


async def test_venda_fora_dos_30_dias_nao_entra(pg_pool, test_seller):
    _u, sid = test_seller
    await _venda(pg_pool, sid, 1, "MLB1", HOJE - timedelta(days=31), 100.0)
    await _custo(pg_pool, sid, "MLB1", 500.0)

    r = await alertas(pg_pool, sid, hoje=HOJE)

    assert r["produtos_avaliados"] == 0


# ---------- anúncio parado ----------


async def _vendas_espacadas(pool, sid, item_id, primeira_id, ultima: date, intervalo: int, n: int):
    for i in range(n):
        dia = ultima - timedelta(days=intervalo * (n - 1 - i))
        await _venda(pool, sid, primeira_id + i, item_id, dia, 50.0)


async def test_parado_e_ficar_tres_vezes_o_intervalo_sem_vender(pg_pool, test_seller):
    _u, sid = test_seller
    await _sincronizado_em(pg_pool, sid, HOJE)
    await _item(pg_pool, sid, "MLB1", "Fone")
    # Vende a cada 8 dias; a última foi há 28: passou de 3 x 8 = 24.
    await _vendas_espacadas(pg_pool, sid, "MLB1", 100, HOJE - timedelta(days=28), 8, 5)
    # Mesmo ritmo, última há 20: ainda dentro de 24.
    await _vendas_espacadas(pg_pool, sid, "MLB2", 200, HOJE - timedelta(days=20), 8, 5)
    # Só 4 dias de venda: sem ritmo para dizer que parou.
    await _vendas_espacadas(pg_pool, sid, "MLB3", 300, HOJE - timedelta(days=60), 8, 4)

    r = await alertas(pg_pool, sid, hoje=HOJE)

    assert r["parados"] == [
        {
            "sku": "MLB1",
            "titulo": "Fone",
            "dias_sem_vender": 28,
            "intervalo_normal": 8,
            "ultima_venda": (HOJE - timedelta(days=28)).isoformat(),
        }
    ]


async def test_produto_de_venda_diaria_para_com_o_minimo_de_7_dias(pg_pool, test_seller):
    """3 x 1 dia = 3: sem o mínimo, um fim de semana fraco viraria alerta."""
    _u, sid = test_seller
    await _sincronizado_em(pg_pool, sid, HOJE)
    await _vendas_espacadas(pg_pool, sid, "MLB1", 100, HOJE - timedelta(days=5), 1, 10)
    await _vendas_espacadas(pg_pool, sid, "MLB2", 200, HOJE - timedelta(days=8), 1, 10)

    r = await alertas(pg_pool, sid, hoje=HOJE)

    assert [a["sku"] for a in r["parados"]] == ["MLB2"]


async def test_dias_parados_contam_ate_a_ultima_sincronizacao(pg_pool, test_seller):
    """Com a sincronização parada, todo produto pareceria parado sem estar."""
    _u, sid = test_seller
    sincronizou = HOJE - timedelta(days=10)
    await _sincronizado_em(pg_pool, sid, sincronizou)
    await _vendas_espacadas(pg_pool, sid, "MLB1", 100, sincronizou - timedelta(days=5), 2, 6)

    r = await alertas(pg_pool, sid, hoje=HOJE)

    # 5 dias até a sincronização (dentro do mínimo de 7); 15 até hoje.
    assert r["parados"] == []


async def test_sem_sincronizacao_nao_ha_parado(pg_pool, test_seller):
    _u, sid = test_seller
    await _vendas_espacadas(pg_pool, sid, "MLB1", 100, HOJE - timedelta(days=40), 2, 6)

    r = await alertas(pg_pool, sid, hoje=HOJE)

    assert r["parados"] == []


# ---------- endpoint ----------


async def test_alertas_sao_do_premium(client, pg_pool, test_seller):
    user_id, sid = test_seller
    resp = client.get("/metrics/alertas", headers=_auth(user_id))
    assert resp.status_code == 200
    assert set(resp.json()) >= {"margem_negativa", "parados", "produtos_avaliados"}

    async with pg_pool.acquire() as conn:
        await da_plano(conn, sid, "exclusive")
    resp = client.get("/metrics/alertas", headers=_auth(user_id))
    assert resp.status_code == 403
    assert resp.json()["detail"]["codigo"] == "fora-do-plano"

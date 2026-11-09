"""Premium: a visão que soma as contas do Mercado Livre do login (parte B).

Spec: docs/specs/2026-11-06-premium-varias-contas-design.md, "Parte B".
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from backend.analytics.alertas_pg import alertas
from backend.analytics.segmentation_pg import abc_pareto, rfm_scores

from .conftest import da_plano
from .test_alertas import HOJE, _custo, _frete, _sincronizado_em, _venda, _vendas_espacadas
from .test_routers import _item, _order, _order_item
from .test_routers_ml import _auth, _conectado
from .test_routers_ml import client as _client
from .test_varias_contas import _extra

client = _client

TODAS = {"X-Conta": "todas"}
JANELA = {"date_from": "2026-07-25", "date_to": "2026-07-26"}


def _fluxo(client, user_id, headers=None):
    return client.get(
        "/metrics/fluxo-financeiro", params=JANELA, headers=_auth(user_id) | (headers or {})
    )


async def _backfill_concluido(pool, seller_id, dias):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sync_jobs (seller_id, kind, status, cursor, finished_at) "
            "VALUES ($1, 'backfill', 'done', $2::jsonb, now())",
            seller_id,
            json.dumps({"dias": dias}),
        )


async def _visita(pool, seller_id, item_id, dia: date, visitas=10):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO item_visits (seller_id, item_id, dia, visitas) VALUES ($1, $2, $3, $4)",
            seller_id,
            item_id,
            dia,
            visitas,
        )


# ---------- acesso ----------


async def test_todas_soma_as_contas(client, pg_pool, test_seller):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0)
    await _order(pg_pool, extra, 2, "2026-07-25T10:00:00+00:00", 700.0)

    resp = _fluxo(client, user_id, TODAS)

    assert resp.status_code == 200
    assert resp.json()[0]["receita_bruta"] == pytest.approx(800.0)


async def test_todas_nao_soma_conta_de_outro_usuario(client, pg_pool, test_seller, outro_seller):
    user_id, sid = test_seller
    _outro, alheia = outro_seller
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0)
    await _order(pg_pool, alheia, 2, "2026-07-25T10:00:00+00:00", 999.0)

    resp = _fluxo(client, user_id, TODAS)

    assert resp.json()[0]["receita_bruta"] == pytest.approx(100.0)


async def test_todas_fora_do_premium_e_recusada(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _extra(pg_pool, user_id)
    async with pg_pool.acquire() as conn:
        await da_plano(conn, sid, "exclusive")

    resp = _fluxo(client, user_id, TODAS)

    assert resp.status_code == 403
    assert resp.json()["detail"]["codigo"] == "conta-invalida"
    resp = client.get("/conta/acesso", headers=_auth(user_id) | TODAS)
    assert resp.status_code == 403


async def test_acesso_diz_que_a_visao_e_somada(client, pg_pool, test_seller):
    user_id, _sid = test_seller
    await _extra(pg_pool, user_id)

    resp = client.get("/conta/acesso", headers=_auth(user_id) | TODAS)

    assert resp.status_code == 200
    assert resp.json()["conta_aberta"] == "todas"


async def test_historico_somado_e_o_menor_entre_as_contas(client, pg_pool, test_seller):
    """Uma conta em 12 meses e outra em 6: mostrar 12 exibiria venda zero na segunda."""
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _backfill_concluido(pg_pool, sid, 365)
    await _backfill_concluido(pg_pool, extra, 180)

    sozinha = client.get("/conta/acesso", headers=_auth(user_id)).json()
    somada = client.get("/conta/acesso", headers=_auth(user_id) | TODAS).json()

    assert sozinha["dias_de_historico"] == 365
    assert somada["dias_de_historico"] == 180
    assert somada["historico_buscando"] is True


# ---------- o que não soma ----------


async def test_gravar_custo_recusa_a_visao_somada(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _extra(pg_pool, user_id)
    await _item(pg_pool, sid, "MLB1", "Fone")

    resp = client.put("/custos/MLB1", json={"custo_unitario": 10.0}, headers=_auth(user_id) | TODAS)

    assert resp.status_code == 409
    assert resp.json()["detail"]["codigo"] == "visao-somada"
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM product_costs") == 0


async def test_desconectar_recusa_a_visao_somada(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _extra(pg_pool, user_id)
    await _conectado(pg_pool, sid)

    resp = client.delete("/ml/connection", headers=_auth(user_id) | TODAS)

    assert resp.status_code == 409
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT ml_seller_id FROM sellers WHERE id = $1", sid)


async def test_sincronizar_ao_entrar_na_visao_somada_nao_enfileira(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _extra(pg_pool, user_id)
    await _conectado(pg_pool, sid)

    login = client.post("/ml/sync", params={"motivo": "login"}, headers=_auth(user_id) | TODAS)
    manual = client.post("/ml/sync", params={"motivo": "manual"}, headers=_auth(user_id) | TODAS)

    assert login.status_code == 200
    assert login.json() == {"enfileirado": False, "motivo": "visao-somada"}
    assert manual.status_code == 409
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM sync_jobs") == 0


async def test_lista_de_custos_soma_para_o_resumo(client, pg_pool, test_seller):
    """O Resumo lê a lista de custos para a cobertura: ela soma, gravar não."""
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    for conta, pedido, item in ((sid, 1, "MLB1"), (extra, 2, "MLB2")):
        await _item(pg_pool, conta, item, item)
        await _order(pg_pool, conta, pedido, "2026-07-25T10:00:00+00:00", 100.0)
        await _order_item(pg_pool, conta, pedido, item, 1, 100.0)

    resp = client.get("/custos", params=JANELA, headers=_auth(user_id) | TODAS)

    assert resp.status_code == 200
    assert {linha["sku"] for linha in resp.json()} == {"MLB1", "MLB2"}


async def test_adicionar_e_remover_conta_funcionam_na_visao_somada(client, pg_pool, test_seller):
    """Agem sobre o login: a lista de contas continua em Conectar."""
    user_id, _sid = test_seller
    extra = await _extra(pg_pool, user_id)

    nova = client.post("/ml/contas/nova", headers=_auth(user_id) | TODAS)
    removida = client.delete(f"/ml/contas/{extra}", headers=_auth(user_id) | TODAS)

    assert nova.status_code == 200
    assert removida.status_code == 204


# ---------- consultas ----------


async def test_frete_de_cada_conta_entra_na_soma(pg_pool, test_seller, client):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _venda(pg_pool, sid, 1, "MLB1", date(2026, 7, 25), 100.0, envio=501)
    await _venda(pg_pool, extra, 2, "MLB2", date(2026, 7, 25), 700.0, envio=502)
    await _frete(pg_pool, sid, 501, 10.0)
    await _frete(pg_pool, extra, 502, 20.0)

    linha = _fluxo(client, user_id, TODAS).json()[0]

    assert linha["frete"] == pytest.approx(30.0)
    assert linha["receita_sem_frete"] == pytest.approx(0.0)


async def test_conversao_usa_o_inicio_da_colheita_de_cada_conta(pg_pool, test_seller):
    """A venda da conta B antes da colheita DELA não entra no numerador da conversão,
    mesmo que a conta A colha visitas desde antes."""
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _visita(pg_pool, sid, "MLB1", date(2026, 6, 1))
    await _visita(pg_pool, extra, "MLB2", date(2026, 7, 20))
    await _venda(pg_pool, extra, 1, "MLB2", date(2026, 7, 10), 50.0)
    await _venda(pg_pool, extra, 2, "MLB2", date(2026, 7, 22), 50.0)

    df = await abc_pareto(pg_pool, [sid, extra], "2026-07-01", "2026-08-01")

    linha = df[df["sku"] == "MLB2"].iloc[0]
    assert linha["unidades"] == 2
    assert linha["unidades_com_visita"] == 1


async def test_comprador_das_duas_contas_conta_uma_vez(pg_pool, test_seller):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _order(pg_pool, sid, 1, "2026-07-10T10:00:00+00:00", 100.0, buyer_id=42)
    await _order(pg_pool, extra, 2, "2026-07-20T10:00:00+00:00", 300.0, buyer_id=42)

    df = await rfm_scores(pg_pool, [sid, extra], "2026-07-01", "2026-08-01")

    assert len(df) == 1
    assert df.iloc[0]["frequency"] == 2
    assert df.iloc[0]["monetary"] == pytest.approx(400.0)


async def test_parado_e_medido_contra_a_sincronizacao_da_propria_conta(pg_pool, test_seller):
    """A conta B parou de sincronizar há 20 dias: contra a data da conta A, todo
    produto dela pareceria parado sem estar."""
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _sincronizado_em(pg_pool, sid, HOJE)
    ref_b = HOJE - timedelta(days=20)
    await _sincronizado_em(pg_pool, extra, ref_b)
    # Ritmo de 2 dias, última venda no dia da sincronização da própria conta.
    await _vendas_espacadas(pg_pool, extra, "MLB2", 200, ref_b, 2, 5)
    # Na conta A, um parado de verdade: 28 dias sem vender, ritmo de 8.
    await _vendas_espacadas(pg_pool, sid, "MLB1", 100, HOJE - timedelta(days=28), 8, 5)

    r = await alertas(pg_pool, [sid, extra], hoje=HOJE)

    assert [a["sku"] for a in r["parados"]] == ["MLB1"]
    assert r["produtos_com_ritmo"] == 2
    # A data mostrada é a mais antiga: é ela que avisa que uma conta está atrasada.
    assert r["referencia"] == ref_b.isoformat()


async def test_margem_negativa_de_qualquer_conta_aparece(pg_pool, test_seller):
    user_id, sid = test_seller
    extra = await _extra(pg_pool, user_id)
    await _venda(pg_pool, sid, 1, "MLB1", HOJE - timedelta(days=3), 100.0)
    await _venda(pg_pool, extra, 2, "MLB2", HOJE - timedelta(days=3), 100.0)
    await _custo(pg_pool, sid, "MLB1", 10.0)
    await _custo(pg_pool, extra, "MLB2", 150.0)

    r = await alertas(pg_pool, [sid, extra], hoje=HOJE)

    assert r["produtos_avaliados"] == 2
    assert [a["sku"] for a in r["margem_negativa"]] == ["MLB2"]

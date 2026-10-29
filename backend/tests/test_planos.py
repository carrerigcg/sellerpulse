"""Planos e controle de acesso.

Cada regra de docs/specs/2026-10-28-planos-e-acesso-design.md tem um teste
aqui. O que cada um prova está no nome; o porquê, na spec.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import responses as responses_lib
from fastapi import HTTPException

from backend.analytics._common import _TZ_VENDEDOR
from backend.ml import oauth
from backend.ml import tokens as tokens_mod
from backend.planos import PLANOS, VERSAO_DOS_TERMOS
from backend.routers._common import CABECALHO_HISTORICO, limita_ao_historico
from backend.routers.segmentation import CABECALHO_PRODUTOS_OCULTOS

from .conftest import da_plano
from .test_routers import _item, _order, _order_item
from .test_routers_ml import (
    SEGREDO,
    _auth,
    _cabecalho,
    _conectado,
    _mock_ml_conexao,
)
from .test_routers_ml import client as _client_ml

ESSENCIAL = PLANOS["essencial"]
EXCLUSIVE = PLANOS["exclusive"]

# O mesmo cliente dos testes de /ml (com as variáveis do OAuth), porque as
# travas de plano cobrem também a conexão e a sincronização.
client = _client_ml


@pytest.fixture
async def seller_sem_plano(pg_pool):
    user_id = uuid.uuid4()
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO auth.users (id, email) VALUES ($1, $2)",
            user_id,
            "semplano@sellerpulse.dev",
        )
        seller_id = await conn.fetchval(
            "INSERT INTO sellers (user_id) VALUES ($1) RETURNING id", user_id
        )
    yield user_id, seller_id
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM auth.users WHERE id = $1", user_id)


async def _no_plano(pool, seller_id, plano, *, aceita=True):
    async with pool.acquire() as conn:
        if not aceita:
            await conn.execute("DELETE FROM aceites_de_termos WHERE seller_id = $1", seller_id)
        await da_plano(conn, seller_id, plano, aceita=aceita)


def _hoje() -> datetime:
    return datetime.now(UTC).astimezone(_TZ_VENDEDOR)


def _dia(dias_atras: int) -> str:
    return (_hoje().date() - timedelta(days=dias_atras)).isoformat()


JANELA = {"date_from": "2026-07-01", "date_to": "2026-08-01"}

# Tudo o que o painel usa e exige plano. A demo fica de fora: é pública.
ROTAS_DO_PAINEL = [
    ("get", "/metrics/fluxo-financeiro", JANELA),
    ("get", "/metrics/cancelamentos", JANELA),
    ("get", "/metrics/top-produtos", JANELA),
    ("get", "/segmentation/abc", JANELA),
    ("get", "/segmentation/rfm", JANELA),
    ("get", "/segmentation/cohort", JANELA),
    ("get", "/custos", JANELA),
    ("post", "/ml/connect/start", None),
    ("post", "/ml/sync", None),
]


# ---------- sem plano: só demo ----------


@pytest.mark.parametrize(("metodo", "rota", "params"), ROTAS_DO_PAINEL)
async def test_sem_plano_o_painel_recusa_com_402(client, seller_sem_plano, metodo, rota, params):
    user_id, _ = seller_sem_plano
    resp = getattr(client, metodo)(rota, params=params, headers=_auth(user_id))
    assert resp.status_code == 402
    assert resp.json()["detail"]["codigo"] == "sem-plano"


async def test_sem_plano_a_demo_continua_aberta(client):
    resp = client.get("/demo/fluxo-financeiro", params=JANELA)
    # A demo pode estar sem seller configurado no teste (503); o que importa
    # é que ela não pede plano.
    assert resp.status_code not in (401, 402, 403)


@pytest.mark.parametrize(("metodo", "rota", "params"), ROTAS_DO_PAINEL)
async def test_com_plano_e_sem_aceite_recusa_com_termos_pendentes(
    client, pg_pool, test_seller, metodo, rota, params
):
    user_id, seller_id = test_seller
    await _no_plano(pg_pool, seller_id, "exclusive", aceita=False)
    resp = getattr(client, metodo)(rota, params=params, headers=_auth(user_id))
    assert resp.status_code == 403
    assert resp.json()["detail"]["codigo"] == "termos-pendentes"


async def test_aceite_de_versao_antiga_nao_libera(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE aceites_de_termos SET versao = 'versao-antiga' WHERE seller_id = $1",
            seller_id,
        )
    resp = client.get("/metrics/fluxo-financeiro", params=JANELA, headers=_auth(user_id))
    assert resp.json()["detail"]["codigo"] == "termos-pendentes"


async def test_callback_do_ml_sem_plano_nao_conecta(client, pg_pool, seller_sem_plano):
    """O state vale por minutos; quem não tem plano não termina a conexão."""
    _, seller_id = seller_sem_plano
    state = oauth.emite_state(str(seller_id))
    # O ML responde como se a conexão fosse dar certo. Sem isso, a troca do
    # código falharia por si só e o teste passaria mesmo sem a trava.
    with responses_lib.RequestsMock(assert_all_requests_are_fired=False) as rsps:
        _mock_ml_conexao(rsps)
        resp = client.get(
            "/ml/callback", params={"code": "TG-x", "state": state}, follow_redirects=False
        )
    assert resp.status_code == 307
    assert resp.headers["location"] == "https://app.exemplo.dev/dashboard"
    assert await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load() is None
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM sync_jobs") == 0


async def test_callback_do_ml_com_plano_conecta(client, pg_pool, test_seller):
    """O par do teste acima: a trava não quebrou a conexão de quem pode."""
    _, seller_id = test_seller
    state = oauth.emite_state(str(seller_id))
    with responses_lib.RequestsMock() as rsps:
        _mock_ml_conexao(rsps)
        client.get("/ml/callback", params={"code": "TG-x", "state": state}, follow_redirects=False)
    assert await tokens_mod.PostgresTokenStore(pg_pool, seller_id).load() is not None


# ---------- Essencial: o que fica com cadeado ----------


@pytest.mark.parametrize("rota", ["/segmentation/rfm", "/segmentation/cohort"])
async def test_essencial_recusa_clientes_e_cohort(client, pg_pool, test_seller, rota):
    user_id, seller_id = test_seller
    await _no_plano(pg_pool, seller_id, "essencial")
    resp = client.get(
        rota, params={"date_from": _dia(30), "date_to": _dia(0)}, headers=_auth(user_id)
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["codigo"] == "fora-do-plano"


@pytest.mark.parametrize("rota", ["/segmentation/rfm", "/segmentation/cohort"])
async def test_exclusive_libera_clientes_e_cohort(client, test_seller, rota):
    user_id, _ = test_seller
    resp = client.get(
        rota, params={"date_from": _dia(30), "date_to": _dia(0)}, headers=_auth(user_id)
    )
    assert resp.status_code == 200


async def _doze_produtos(pool, seller_id):
    """12 produtos com receitas distintas, vendidos ontem."""
    ontem = f"{_dia(1)}T12:00:00-03:00"
    for i in range(12):
        await _item(pool, seller_id, f"MLB{i}", f"Produto {i}")
        await _order(pool, seller_id, i + 1, ontem, 1000.0 - i * 50)
        await _order_item(pool, seller_id, i + 1, f"MLB{i}", 1, 1000.0 - i * 50)


async def test_essencial_ve_so_os_10_primeiros_da_abc_sem_visitas(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _doze_produtos(pg_pool, seller_id)
    params = {"date_from": _dia(30), "date_to": _dia(0)}

    completa = client.get("/segmentation/abc", params=params, headers=_auth(user_id)).json()
    await _no_plano(pg_pool, seller_id, "essencial")
    resp = client.get("/segmentation/abc", params=params, headers=_auth(user_id))

    assert resp.status_code == 200
    corte = resp.json()
    assert [p["sku"] for p in corte] == [p["sku"] for p in completa[:10]]
    assert resp.headers[CABECALHO_PRODUTOS_OCULTOS] == "2"
    # Classe e acumulado vêm da curva inteira, não reclassificados em 10.
    assert [p["classe"] for p in corte] == [p["classe"] for p in completa[:10]]
    assert corte[-1]["receita_acumulada_pct"] < 100
    for coluna in ("visitas", "conversao", "unidades_com_visita"):
        assert coluna not in corte[0]


async def test_exclusive_ve_a_abc_inteira_com_visitas(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _doze_produtos(pg_pool, seller_id)
    resp = client.get(
        "/segmentation/abc",
        params={"date_from": _dia(30), "date_to": _dia(0)},
        headers=_auth(user_id),
    )
    assert len(resp.json()) == 12
    assert "visitas" in resp.json()[0]
    assert CABECALHO_PRODUTOS_OCULTOS not in resp.headers


# ---------- Essencial: histórico de 90 dias ----------


async def test_essencial_corta_a_janela_no_limite_do_historico(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _order(pg_pool, seller_id, 1, f"{_dia(100)}T12:00:00-03:00", 500.0)
    await _order(pg_pool, seller_id, 2, f"{_dia(10)}T12:00:00-03:00", 70.0)
    await _no_plano(pg_pool, seller_id, "essencial")

    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": _dia(120), "date_to": _dia(0)},
        headers=_auth(user_id),
    )

    assert resp.status_code == 200
    assert resp.headers[CABECALHO_HISTORICO] == _dia(90)
    receita = sum(linha["receita_bruta"] for linha in resp.json())
    assert receita == pytest.approx(70.0)


async def test_essencial_recusa_janela_inteira_antes_do_limite(client, pg_pool, test_seller):
    """O período anterior da comparação não pode voltar vazio: vazio é zero."""
    user_id, seller_id = test_seller
    await _no_plano(pg_pool, seller_id, "essencial")
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": _dia(180), "date_to": _dia(90)},
        headers=_auth(user_id),
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["codigo"] == "fora-do-plano"


async def test_essencial_a_janela_padrao_de_90_dias_cabe_inteira(client, pg_pool, test_seller):
    """`periodoPadrao` do front pede de hoje-90 a hoje: não pode virar corte."""
    user_id, seller_id = test_seller
    await _no_plano(pg_pool, seller_id, "essencial")
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": _dia(90), "date_to": _dia(0)},
        headers=_auth(user_id),
    )
    assert resp.status_code == 200
    assert CABECALHO_HISTORICO not in resp.headers


async def test_exclusive_nao_corta_historico(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _order(pg_pool, seller_id, 1, f"{_dia(100)}T12:00:00-03:00", 500.0)
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": _dia(120), "date_to": _dia(0)},
        headers=_auth(user_id),
    )
    assert CABECALHO_HISTORICO not in resp.headers
    assert sum(linha["receita_bruta"] for linha in resp.json()) == pytest.approx(500.0)


def test_o_limite_do_historico_e_contado_no_dia_do_vendedor():
    # 23h de 28/10 em Brasília já é 29/10 em UTC. Contado em UTC, o limite
    # cairia um dia depois e cortaria a janela padrão de quem abre o painel
    # à noite.
    agora = datetime(2026, 10, 29, 2, 0, tzinfo=UTC)
    de, ate, cortado = limita_ao_historico(ESSENCIAL, "2026-07-01", "2026-10-28", agora=agora)
    assert (de, ate, cortado) == ("2026-07-30", "2026-10-28", "2026-07-30")
    assert limita_ao_historico(ESSENCIAL, "2026-07-30", "2026-10-28", agora=agora)[2] is None


def test_janela_que_termina_no_limite_e_recusada():
    agora = datetime(2026, 10, 29, 2, 0, tzinfo=UTC)
    with pytest.raises(HTTPException) as erro:
        limita_ao_historico(ESSENCIAL, "2026-06-01", "2026-07-30", agora=agora)
    assert erro.value.status_code == 403


def test_plano_sem_limite_nao_mexe_na_janela():
    assert limita_ao_historico(EXCLUSIVE, "2020-01-01", "2026-10-28") == (
        "2020-01-01",
        "2026-10-28",
        None,
    )


# ---------- Essencial: só a sincronização diária ----------


async def test_essencial_nao_sincroniza_no_login(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _conectado(pg_pool, seller_id, ultimo_sync=datetime.now(UTC) - timedelta(days=2))
    await _no_plano(pg_pool, seller_id, "essencial")
    resp = client.post("/ml/sync", params={"motivo": "login"}, headers=_auth(user_id))
    assert resp.status_code == 200
    assert resp.json() == {"enfileirado": False, "motivo": "plano"}
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM sync_jobs") == 0


async def test_essencial_nao_sincroniza_pelo_botao(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _conectado(pg_pool, seller_id, ultimo_sync=datetime.now(UTC) - timedelta(days=2))
    await _no_plano(pg_pool, seller_id, "essencial")
    resp = client.post("/ml/sync", params={"motivo": "manual"}, headers=_auth(user_id))
    assert resp.status_code == 403
    async with pg_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM sync_jobs") == 0


async def test_essencial_entra_na_sincronizacao_diaria(client, monkeypatch, pg_pool, test_seller):
    monkeypatch.setenv("SYNC_SECRET", SEGREDO)
    _, seller_id = test_seller
    await _conectado(pg_pool, seller_id, ultimo_sync=datetime.now(UTC) - timedelta(days=2))
    await _no_plano(pg_pool, seller_id, "essencial")
    assert client.post("/ml/sync-todos", headers=_cabecalho()).json()["enfileirados"] == 1


async def test_sincronizacao_diaria_pula_quem_nao_tem_plano(
    client, monkeypatch, pg_pool, test_seller, seller_sem_plano
):
    monkeypatch.setenv("SYNC_SECRET", SEGREDO)
    _, com_plano = test_seller
    _, sem_plano = seller_sem_plano
    velho = datetime.now(UTC) - timedelta(days=2)
    await _conectado(pg_pool, com_plano, ultimo_sync=velho, ml_seller_id=111)
    await _conectado(pg_pool, sem_plano, ultimo_sync=velho, ml_seller_id=222)

    resp = client.post("/ml/sync-todos", headers=_cabecalho())

    assert resp.json()["sellers"] == 1
    async with pg_pool.acquire() as conn:
        alvos = await conn.fetch("SELECT seller_id FROM sync_jobs")
    assert [r["seller_id"] for r in alvos] == [com_plano]


# ---------- /conta: acesso e aceite ----------


async def test_acesso_sem_plano(client, seller_sem_plano):
    user_id, _ = seller_sem_plano
    resp = client.get("/conta/acesso", headers=_auth(user_id))
    assert resp.status_code == 200
    assert resp.json()["plano"] is None
    assert resp.json()["termos"] == {"versao": VERSAO_DOS_TERMOS, "aceito": False}


async def test_acesso_do_essencial_lista_o_que_ele_libera(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _no_plano(pg_pool, seller_id, "essencial")
    corpo = client.get("/conta/acesso", headers=_auth(user_id)).json()
    assert corpo["plano"] == "essencial"
    assert corpo["recursos"] == []
    assert corpo["dias_de_historico"] == 90
    assert corpo["produtos_na_abc"] == 10
    assert corpo["termos"]["aceito"] is True


async def test_acesso_do_exclusive_libera_tudo(client, test_seller):
    user_id, _ = test_seller
    corpo = client.get("/conta/acesso", headers=_auth(user_id)).json()
    assert "clientes" in corpo["recursos"]
    assert corpo["dias_de_historico"] is None


async def test_aceite_sem_plano_e_recusado(client, pg_pool, seller_sem_plano):
    user_id, seller_id = seller_sem_plano
    resp = client.post("/conta/aceite", json={"versao": VERSAO_DOS_TERMOS}, headers=_auth(user_id))
    assert resp.status_code == 402
    async with pg_pool.acquire() as conn:
        n = await conn.fetchval(
            "SELECT count(*) FROM aceites_de_termos WHERE seller_id = $1", seller_id
        )
    assert n == 0


async def test_aceite_de_versao_que_nao_e_a_vigente_e_recusado(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _no_plano(pg_pool, seller_id, "essencial", aceita=False)
    resp = client.post("/conta/aceite", json={"versao": "outra"}, headers=_auth(user_id))
    assert resp.status_code == 409
    corpo = client.get("/conta/acesso", headers=_auth(user_id)).json()
    assert corpo["termos"]["aceito"] is False


async def test_aceite_grava_a_prova_e_libera_o_painel(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _no_plano(pg_pool, seller_id, "essencial", aceita=False)
    cabecalhos = {**_auth(user_id), "User-Agent": "navegador-de-teste"}

    resp = client.post("/conta/aceite", json={"versao": VERSAO_DOS_TERMOS}, headers=cabecalhos)
    assert resp.status_code == 201
    # Aceitar de novo não duplica a prova.
    client.post("/conta/aceite", json={"versao": VERSAO_DOS_TERMOS}, headers=cabecalhos)

    async with pg_pool.acquire() as conn:
        provas = await conn.fetch(
            "SELECT versao, ip, user_agent FROM aceites_de_termos WHERE seller_id = $1", seller_id
        )
    assert len(provas) == 1
    assert provas[0]["versao"] == VERSAO_DOS_TERMOS
    assert provas[0]["user_agent"] == "navegador-de-teste"
    assert provas[0]["ip"]
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": _dia(30), "date_to": _dia(0)},
        headers=_auth(user_id),
    )
    assert resp.status_code == 200


async def test_status_diz_se_o_plano_sincroniza_sob_demanda(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    status = client.get("/ml/sync/status", headers=_auth(user_id)).json()
    assert status["sincroniza_sob_demanda"] is True
    await _no_plano(pg_pool, seller_id, "essencial")
    status = client.get("/ml/sync/status", headers=_auth(user_id)).json()
    assert status["sincroniza_sob_demanda"] is False

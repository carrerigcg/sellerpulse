"""Cobrança pelo Asaas: contratar, webhook, troca, cancelamento e prazo do acesso.

Cada regra de docs/specs/2026-10-29-cobranca-asaas-design.md tem um teste
aqui. O Asaas é falso (um `httpx.MockTransport`), e os eventos do webhook
seguem os formatos da documentação.
"""

from __future__ import annotations

import json
import pathlib
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from backend.pagamentos import asaas, eventos
from backend.pagamentos.prazos import fim_do_periodo, meia_noite_do_vendedor
from backend.planos import PLANOS, VERSAO_DOS_TERMOS

from .conftest import da_plano
from .test_routers_ml import SEGREDO, _auth, _cabecalho, _conectado
from .test_routers_ml import client as _client_ml

client = _client_ml

TOKEN_DO_WEBHOOK = "token-do-webhook-de-teste"
HOJE = date(2026, 11, 2)


@pytest.fixture(autouse=True)
async def _eventos_limpos(pg_pool):
    """`eventos_do_gateway` não é de nenhum vendedor, então o teardown dos
    sellers não a limpa. Sem isto, o id de evento de um teste vira "repetido"
    no seguinte."""
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM eventos_do_gateway")
    yield


class AsaasFalso:
    """Guarda o que foi pedido ao Asaas e responde como ele."""

    def __init__(self) -> None:
        self.pedidos: list[tuple[str, str, dict | None]] = []
        self.status = 200

    def __call__(self, request: httpx.Request) -> httpx.Response:
        corpo = json.loads(request.content) if request.content else None
        self.pedidos.append((request.method, request.url.path, corpo))
        assert request.headers["access_token"] == "chave-de-teste"
        if self.status != 200:
            return httpx.Response(self.status, json={"errors": [{"description": "recusado"}]})
        if request.method == "POST" and request.url.path.endswith("/checkouts"):
            return httpx.Response(
                200, json={"id": f"chk_{len(self.pedidos)}", "link": "https://asaas.test/c/1"}
            )
        return httpx.Response(200, json={"ok": True})


@pytest.fixture
def asaas_falso(monkeypatch):
    falso = AsaasFalso()
    monkeypatch.setenv("ASAAS_API_KEY", "chave-de-teste")
    monkeypatch.setenv("ASAAS_WEBHOOK_TOKEN", TOKEN_DO_WEBHOOK)
    monkeypatch.setattr(
        asaas,
        "_cliente",
        lambda: httpx.AsyncClient(
            base_url="https://asaas.test/v3",
            headers={"access_token": "chave-de-teste"},
            transport=httpx.MockTransport(falso),
        ),
    )
    return falso


@pytest.fixture
async def sem_plano(pg_pool):
    user_id = uuid.uuid4()
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO auth.users (id, email) VALUES ($1, $2)", user_id, "novo@sellerpulse.dev"
        )
        seller_id = await conn.fetchval(
            "INSERT INTO sellers (user_id) VALUES ($1) RETURNING id", user_id
        )
    yield user_id, seller_id
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM auth.users WHERE id = $1", user_id)


def _contratacao(**muda) -> dict:
    corpo = {
        "plano": "exclusive",
        "ciclo": "mensal",
        "versao_dos_termos": VERSAO_DOS_TERMOS,
        "nome": "Loja de Teste",
        "cpf_cnpj": "123.456.789-09",
        "email": "loja@teste.dev",
    }
    corpo.update(muda)
    return corpo


# ---------- prazos ----------


def test_um_mes_depois_de_31_de_janeiro_e_o_fim_de_fevereiro():
    assert fim_do_periodo(date(2026, 1, 31), "mensal") == date(2026, 2, 28)


def test_o_anual_cobre_doze_meses():
    assert fim_do_periodo(date(2026, 11, 2), "anual") == date(2027, 11, 2)


def test_o_anual_custa_dez_mensais():
    assert PLANOS["essencial"].preco("anual") == Decimal("499.20")
    assert PLANOS["exclusive"].preco("anual") == Decimal("799.70")
    assert PLANOS["premium"].preco("anual") == Decimal("1399.50")


def test_os_precos_da_vitrine_batem_com_os_do_backend():
    """A vitrine mostra um número; o checkout cobra outro. Isso não pode divergir."""
    raiz = pathlib.Path(__file__).resolve().parents[2]
    precos = (raiz / "frontend/lib/precos.ts").read_text(encoding="utf-8")
    bloco = precos[precos.index("PRECOS_MENSAIS") : precos.index("};")]
    na_vitrine = dict(re.findall(r"(\w+): ([\d.]+),", bloco))
    assert {nome: Decimal(preco) for nome, preco in na_vitrine.items()} == {
        nome: plano.preco_mensal for nome, plano in PLANOS.items()
    }


# ---------- contratar ----------


async def test_contratar_sem_o_asaas_configurado_responde_503(client, sem_plano, monkeypatch):
    monkeypatch.delenv("ASAAS_API_KEY", raising=False)
    user_id, _ = sem_plano
    resp = client.post("/conta/checkout", json=_contratacao(), headers=_auth(user_id))
    assert resp.status_code == 503
    assert resp.json()["detail"]["codigo"] == "cobranca-indisponivel"


async def test_contratar_o_exclusive_mensal_grava_o_aceite_e_abre_o_teste(
    client, pg_pool, sem_plano, asaas_falso
):
    user_id, seller_id = sem_plano
    resp = client.post("/conta/checkout", json=_contratacao(), headers=_auth(user_id))

    assert resp.status_code == 201
    assert resp.json() == {"link": "https://asaas.test/c/1", "teste": True}
    metodo, caminho, corpo = asaas_falso.pedidos[0]
    assert (metodo, caminho) == ("POST", "/v3/checkouts")
    assert corpo["chargeTypes"] == ["RECURRENT"]
    assert corpo["billingTypes"] == ["CREDIT_CARD"]
    assert corpo["items"][0]["value"] == 79.97
    assert corpo["subscription"]["cycle"] == "MONTHLY"
    assert corpo["subscription"]["nextDueDate"] == (date.today() + timedelta(days=7)).isoformat()
    assert corpo["customerData"]["cpfCnpj"] == "12345678909"

    async with pg_pool.acquire() as conn:
        aceite = await conn.fetchval(
            "SELECT versao FROM aceites_de_termos WHERE seller_id = $1", seller_id
        )
        checkout = await conn.fetchrow("SELECT * FROM checkouts WHERE seller_id = $1", seller_id)
        plano = await conn.fetchval("SELECT plano FROM assinaturas WHERE seller_id = $1", seller_id)
    assert aceite == VERSAO_DOS_TERMOS
    assert (checkout["plano"], checkout["ciclo"]) == ("exclusive", "mensal")
    # Só o pagamento confirmado libera: abrir o checkout não dá plano.
    assert plano is None


async def test_contratar_o_anual_e_pagamento_unico_por_pix_ou_cartao(
    client, sem_plano, asaas_falso
):
    user_id, _ = sem_plano
    resp = client.post(
        "/conta/checkout",
        json=_contratacao(plano="essencial", ciclo="anual"),
        headers=_auth(user_id),
    )
    assert resp.json()["teste"] is False
    corpo = asaas_falso.pedidos[0][2]
    assert corpo["chargeTypes"] == ["DETACHED"]
    assert set(corpo["billingTypes"]) == {"CREDIT_CARD", "PIX"}
    assert corpo["items"][0]["value"] == 499.2
    assert "subscription" not in corpo


async def test_so_o_exclusive_mensal_tem_teste(client, sem_plano, asaas_falso):
    user_id, _ = sem_plano
    resp = client.post(
        "/conta/checkout", json=_contratacao(plano="premium"), headers=_auth(user_id)
    )
    assert resp.json()["teste"] is False
    assert asaas_falso.pedidos[0][2]["subscription"]["nextDueDate"] == date.today().isoformat()


async def test_o_cpf_nao_fica_guardado(client, pg_pool, sem_plano, asaas_falso):
    user_id, seller_id = sem_plano
    client.post("/conta/checkout", json=_contratacao(), headers=_auth(user_id))
    async with pg_pool.acquire() as conn:
        linhas = await conn.fetch(
            "SELECT row_to_json(c)::text AS t FROM checkouts c WHERE seller_id = $1 "
            "UNION ALL SELECT row_to_json(a)::text FROM aceites_de_termos a WHERE seller_id = $1",
            seller_id,
        )
    assert linhas
    assert all("12345678909" not in linha["t"] for linha in linhas)


async def test_contratar_com_versao_velha_dos_termos_nao_abre_checkout(
    client, sem_plano, asaas_falso
):
    user_id, _ = sem_plano
    resp = client.post(
        "/conta/checkout", json=_contratacao(versao_dos_termos="velha"), headers=_auth(user_id)
    )
    assert resp.status_code == 409
    assert asaas_falso.pedidos == []


async def test_contratar_com_cpf_invalido_e_recusado(client, sem_plano, asaas_falso):
    user_id, _ = sem_plano
    resp = client.post(
        "/conta/checkout", json=_contratacao(cpf_cnpj="123.456.789"), headers=_auth(user_id)
    )
    assert resp.status_code == 422
    assert asaas_falso.pedidos == []


async def test_quem_ja_tem_plano_nao_abre_segundo_checkout(client, test_seller, asaas_falso):
    user_id, _ = test_seller
    resp = client.post("/conta/checkout", json=_contratacao(), headers=_auth(user_id))
    assert resp.status_code == 409
    assert asaas_falso.pedidos == []


async def test_asaas_recusando_o_checkout_vira_502_sem_registro(
    client, pg_pool, sem_plano, asaas_falso
):
    asaas_falso.status = 400
    user_id, seller_id = sem_plano
    resp = client.post("/conta/checkout", json=_contratacao(), headers=_auth(user_id))
    assert resp.status_code == 502
    async with pg_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM checkouts WHERE seller_id = $1", seller_id)
            == 0
        )


# ---------- webhook: autenticação ----------


async def test_webhook_sem_segredo_configurado_recusa(client, monkeypatch):
    monkeypatch.delenv("ASAAS_WEBHOOK_TOKEN", raising=False)
    resp = client.post("/pagamentos/webhook", json={"id": "evt_1", "event": "X"})
    assert resp.status_code == 503


async def test_webhook_com_token_errado_recusa(client, asaas_falso):
    resp = client.post(
        "/pagamentos/webhook",
        json={"id": "evt_1", "event": "X"},
        headers={"asaas-access-token": "chute"},
    )
    assert resp.status_code == 401


async def test_webhook_responde_200_ao_evento_que_ignora(client, asaas_falso):
    resp = client.post(
        "/pagamentos/webhook",
        json={"id": "evt_qualquer", "event": "PAYMENT_CREATED", "payment": {}},
        headers={"asaas-access-token": TOKEN_DO_WEBHOOK},
    )
    assert resp.status_code == 200
    assert resp.json() == {"resultado": "ignorado"}


# ---------- webhook: o que cada evento faz ----------


async def _checkout_criado(pool, seller_id, plano="exclusive", ciclo="mensal", checkout_id="chk_1"):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO checkouts (id, seller_id, plano, ciclo) VALUES ($1, $2, $3, $4)",
            checkout_id,
            seller_id,
            plano,
            ciclo,
        )


def _checkout_pago(evento_id="evt_chk", checkout_id="chk_1"):
    return {
        "id": evento_id,
        "event": "CHECKOUT_PAID",
        "checkout": {"id": checkout_id, "customer": "cus_1", "subscription": "sub_1"},
    }


def _pagamento(evento_id, vencimento: date, tipo="PAYMENT_CONFIRMED", assinatura="sub_1"):
    return {
        "id": evento_id,
        "event": tipo,
        "payment": {
            "id": f"pay_{evento_id}",
            "customer": "cus_1",
            "subscription": assinatura,
            "dueDate": vencimento.isoformat(),
        },
    }


async def _assinatura(pool, seller_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM assinaturas WHERE seller_id = $1", seller_id)


async def test_checkout_pago_com_teste_libera_ate_o_oitavo_dia_mais_tolerancia(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)

    assert await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE) == "plano-ativado"

    linha = await _assinatura(pg_pool, seller_id)
    assert (linha["plano"], linha["origem"], linha["ciclo"]) == ("exclusive", "gateway", "mensal")
    assert (linha["asaas_cliente"], linha["asaas_assinatura"]) == ("cus_1", "sub_1")
    assert linha["pago_ate"] == meia_noite_do_vendedor(HOJE + timedelta(days=7))
    assert linha["acesso_ate"] == meia_noite_do_vendedor(HOJE + timedelta(days=14))


async def test_checkout_pago_sem_teste_libera_o_periodo_inteiro(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id, plano="essencial", ciclo="anual")
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    linha = await _assinatura(pg_pool, seller_id)
    assert linha["pago_ate"] == meia_noite_do_vendedor(date(2027, 11, 2))
    assert linha["acesso_ate"] == meia_noite_do_vendedor(date(2027, 11, 9))


async def test_o_mesmo_evento_duas_vezes_conta_uma(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    vencimento = HOJE + timedelta(days=7)
    assert await eventos.processa(pg_pool, _pagamento("evt_p1", vencimento)) == "prazo-estendido"
    antes = await _assinatura(pg_pool, seller_id)
    assert await eventos.processa(pg_pool, _pagamento("evt_p1", vencimento)) == "repetido"
    assert await _assinatura(pg_pool, seller_id) == antes


async def test_checkout_que_nao_foi_criado_aqui_nao_ativa_nada(pg_pool, sem_plano):
    _, seller_id = sem_plano
    assert (
        await eventos.processa(pg_pool, _checkout_pago(checkout_id="chk_alheio"), hoje=HOJE)
        == "checkout-desconhecido"
    )
    assert await _assinatura(pg_pool, seller_id) is None


async def test_pagamento_confirmado_empurra_o_prazo_um_ciclo(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    vencimento = HOJE + timedelta(days=7)

    await eventos.processa(pg_pool, _pagamento("evt_p1", vencimento))

    linha = await _assinatura(pg_pool, seller_id)
    assert linha["pago_ate"] == meia_noite_do_vendedor(fim_do_periodo(vencimento, "mensal"))
    assert linha["acesso_ate"] == linha["pago_ate"] + timedelta(days=7)


async def test_recebimento_atrasado_de_um_periodo_antigo_nao_encurta_o_prazo(pg_pool, sem_plano):
    """No cartão, o PAYMENT_RECEIVED chega 32 dias depois do CONFIRMED."""
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    primeiro = HOJE + timedelta(days=7)
    segundo = fim_do_periodo(primeiro, "mensal")
    await eventos.processa(pg_pool, _pagamento("evt_p1", primeiro))
    await eventos.processa(pg_pool, _pagamento("evt_p2", segundo))
    antes = await _assinatura(pg_pool, seller_id)

    await eventos.processa(pg_pool, _pagamento("evt_p1r", primeiro, tipo="PAYMENT_RECEIVED"))

    assert (await _assinatura(pg_pool, seller_id))["acesso_ate"] == antes["acesso_ate"]


async def test_downgrade_so_vale_no_pagamento_do_proximo_periodo(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    primeiro = HOJE + timedelta(days=7)
    await eventos.processa(pg_pool, _pagamento("evt_p1", primeiro))
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET plano_no_proximo_ciclo = 'essencial' WHERE seller_id = $1",
            seller_id,
        )

    # O recebimento atrasado do período que já estava pago não aplica.
    await eventos.processa(pg_pool, _pagamento("evt_p1r", primeiro, tipo="PAYMENT_RECEIVED"))
    assert (await _assinatura(pg_pool, seller_id))["plano"] == "exclusive"

    # O pagamento do período seguinte aplica.
    await eventos.processa(pg_pool, _pagamento("evt_p2", fim_do_periodo(primeiro, "mensal")))
    linha = await _assinatura(pg_pool, seller_id)
    assert (linha["plano"], linha["plano_no_proximo_ciclo"]) == ("essencial", None)


async def test_pagamento_de_assinatura_desconhecida_nao_derruba_nada(pg_pool):
    assert (
        await eventos.processa(pg_pool, _pagamento("evt_x", HOJE, assinatura="sub_alheia"))
        == "pagamento-sem-dono"
    )


async def test_assinatura_removida_corta_no_fim_do_periodo_pago(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    evento = {"id": "evt_del", "event": "SUBSCRIPTION_DELETED", "subscription": {"id": "sub_1"}}

    assert await eventos.processa(pg_pool, evento) == "encerrada"

    linha = await _assinatura(pg_pool, seller_id)
    assert linha["acesso_ate"] == linha["pago_ate"]


async def test_estorno_encurta_o_acesso_para_a_tolerancia(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id, plano="premium", ciclo="anual")
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)

    await eventos.processa(pg_pool, _pagamento("evt_r", HOJE, tipo="PAYMENT_REFUNDED"))

    linha = await _assinatura(pg_pool, seller_id)
    assert linha["acesso_ate"] <= datetime.now(UTC) + timedelta(days=7, minutes=1)


async def test_evento_que_falha_ao_aplicar_nao_fica_marcado_como_visto(pg_pool, sem_plano):
    """Se aplicar quebra, o reenvio do Asaas precisa poder tentar de novo."""
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    quebrado = _pagamento("evt_quebrado", HOJE)
    quebrado["payment"]["dueDate"] = "nao-e-data"

    with pytest.raises(ValueError):
        await eventos.processa(pg_pool, quebrado)

    async with pg_pool.acquire() as conn:
        assert (
            await conn.fetchval("SELECT count(*) FROM eventos_do_gateway WHERE id = 'evt_quebrado'")
            == 0
        )


# ---------- o prazo decide o acesso ----------


async def _com_prazo(pool, seller_id, acesso_ate):
    async with pool.acquire() as conn:
        await da_plano(conn, seller_id, "exclusive")
        await conn.execute(
            "UPDATE assinaturas SET acesso_ate = $2 WHERE seller_id = $1", seller_id, acesso_ate
        )


async def test_plano_vencido_volta_a_ser_so_demo(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _com_prazo(pg_pool, seller_id, datetime.now(UTC) - timedelta(minutes=1))
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": "2026-10-01", "date_to": "2026-10-02"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 402


async def test_plano_no_prazo_continua_liberado(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _com_prazo(pg_pool, seller_id, datetime.now(UTC) + timedelta(days=1))
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": "2026-10-01", "date_to": "2026-10-02"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 200


async def test_sincronizacao_diaria_pula_plano_vencido(client, monkeypatch, pg_pool, test_seller):
    monkeypatch.setenv("SYNC_SECRET", SEGREDO)
    _, seller_id = test_seller
    await _conectado(pg_pool, seller_id, ultimo_sync=datetime.now(UTC) - timedelta(days=2))
    await _com_prazo(pg_pool, seller_id, datetime.now(UTC) - timedelta(minutes=1))
    assert client.post("/ml/sync-todos", headers=_cabecalho()).json()["sellers"] == 0


async def test_acesso_mostra_a_assinatura_mesmo_vencida(client, pg_pool, test_seller):
    user_id, seller_id = test_seller
    await _com_prazo(pg_pool, seller_id, datetime.now(UTC) - timedelta(minutes=1))
    corpo = client.get("/conta/acesso", headers=_auth(user_id)).json()
    assert corpo["plano"] is None
    assert corpo["assinatura"]["acesso_ate"] is not None


# ---------- trocar e cancelar ----------


async def _assinante(pool, seller_id, plano="exclusive"):
    async with pool.acquire() as conn:
        await da_plano(conn, seller_id, plano)
        await conn.execute(
            """
            UPDATE assinaturas SET origem = 'gateway', ciclo = 'mensal', asaas_assinatura = 'sub_9',
                   pago_ate = $2, acesso_ate = $3
            WHERE seller_id = $1
            """,
            seller_id,
            datetime.now(UTC) + timedelta(days=10),
            datetime.now(UTC) + timedelta(days=17),
        )


async def test_upgrade_vale_na_hora_e_o_valor_novo_na_proxima_cobranca(
    client, pg_pool, test_seller, asaas_falso
):
    user_id, seller_id = test_seller
    await _assinante(pg_pool, seller_id, "essencial")
    resp = client.post("/conta/plano", json={"plano": "premium"}, headers=_auth(user_id))
    assert resp.json() == {"plano": "premium", "no_proximo_ciclo": None}
    assert asaas_falso.pedidos == [("PUT", "/v3/subscriptions/sub_9", {"value": 139.95})]
    assert (await _assinatura(pg_pool, seller_id))["plano"] == "premium"


async def test_downgrade_fica_para_o_proximo_ciclo(client, pg_pool, test_seller, asaas_falso):
    user_id, seller_id = test_seller
    await _assinante(pg_pool, seller_id, "premium")
    resp = client.post("/conta/plano", json={"plano": "essencial"}, headers=_auth(user_id))
    assert resp.json() == {"plano": "premium", "no_proximo_ciclo": "essencial"}
    assert asaas_falso.pedidos == [("PUT", "/v3/subscriptions/sub_9", {"value": 49.92})]
    linha = await _assinatura(pg_pool, seller_id)
    assert (linha["plano"], linha["plano_no_proximo_ciclo"]) == ("premium", "essencial")


async def test_trocar_plano_dado_a_mao_e_recusado(client, test_seller, asaas_falso):
    user_id, _ = test_seller
    resp = client.post("/conta/plano", json={"plano": "premium"}, headers=_auth(user_id))
    assert resp.status_code == 409
    assert asaas_falso.pedidos == []


async def test_cancelar_mantem_o_acesso_ate_o_fim_do_periodo_pago(
    client, pg_pool, test_seller, asaas_falso
):
    user_id, seller_id = test_seller
    await _assinante(pg_pool, seller_id)
    resp = client.post("/conta/cancelar", headers=_auth(user_id))
    assert resp.status_code == 200
    assert asaas_falso.pedidos == [("DELETE", "/v3/subscriptions/sub_9", None)]
    linha = await _assinatura(pg_pool, seller_id)
    assert linha["acesso_ate"] == linha["pago_ate"]


async def test_cancelada_aparece_e_nao_deixa_trocar_nem_cancelar_de_novo(
    client, pg_pool, test_seller, asaas_falso
):
    user_id, seller_id = test_seller
    await _assinante(pg_pool, seller_id)
    client.post("/conta/cancelar", headers=_auth(user_id))

    assinatura = client.get("/conta/acesso", headers=_auth(user_id)).json()["assinatura"]
    assert (assinatura["cancelada"], assinatura["recorrente"]) == (True, False)
    assert client.post("/conta/cancelar", headers=_auth(user_id)).status_code == 409
    resp = client.post("/conta/plano", json={"plano": "premium"}, headers=_auth(user_id))
    assert resp.status_code == 409


async def test_pagamento_atrasado_nao_devolve_a_tolerancia_a_quem_cancelou(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    primeiro = HOJE + timedelta(days=7)
    await eventos.processa(pg_pool, _pagamento("evt_p1", primeiro))
    cancelamento = {
        "id": "evt_del",
        "event": "SUBSCRIPTION_DELETED",
        "subscription": {"id": "sub_1"},
    }
    await eventos.processa(pg_pool, cancelamento)

    await eventos.processa(pg_pool, _pagamento("evt_p1r", primeiro, tipo="PAYMENT_RECEIVED"))

    linha = await _assinatura(pg_pool, seller_id)
    assert linha["acesso_ate"] == linha["pago_ate"]

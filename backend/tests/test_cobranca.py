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
from backend.pagamentos.prazos import fim_do_periodo, hoje_do_vendedor, meia_noite_do_vendedor
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
        self.assinatura_no_asaas = "sub_api"

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
        if request.method == "GET" and request.url.path.endswith("/subscriptions"):
            return httpx.Response(200, json={"data": [{"id": self.assinatura_no_asaas}]})
        return httpx.Response(200, json={"ok": True})


@pytest.fixture
def asaas_falso(monkeypatch):
    falso = AsaasFalso()
    monkeypatch.setenv("ASAAS_API_KEY", "chave-de-teste")
    monkeypatch.setenv("ASAAS_WEBHOOK_TOKEN", TOKEN_DO_WEBHOOK)
    monkeypatch.setenv("VENDAS_ABERTAS", "1")
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
    }
    corpo.update(muda)
    return corpo


# ---------- prazos ----------


def test_um_mes_depois_de_31_de_janeiro_e_o_fim_de_fevereiro():
    assert fim_do_periodo(date(2026, 1, 31), "mensal") == date(2026, 2, 28)


def test_o_anual_cobre_doze_meses():
    assert fim_do_periodo(date(2026, 11, 2), "anual") == date(2027, 11, 2)


def test_o_anual_custa_dez_mensais():
    assert PLANOS["essencial"].preco("anual") == Decimal("499.00")
    assert PLANOS["exclusive"].preco("anual") == Decimal("799.00")
    assert PLANOS["premium"].preco("anual") == Decimal("1399.00")


@pytest.mark.parametrize("arquivo", ["termos-de-uso.md", "politica-de-privacidade.md"])
def test_os_textos_publicados_trazem_a_versao_que_o_aceite_grava(arquivo):
    raiz = pathlib.Path(__file__).resolve().parents[2]
    texto = (raiz / "frontend" / "content" / "legal" / arquivo).read_text(encoding="utf-8")
    assert f"**Versão:** {VERSAO_DOS_TERMOS}" in texto


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
    monkeypatch.setenv("VENDAS_ABERTAS", "1")
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
    assert corpo["items"][0]["value"] == 79.9
    assert corpo["subscription"]["cycle"] == "MONTHLY"
    assert (
        corpo["subscription"]["nextDueDate"] == (hoje_do_vendedor() + timedelta(days=7)).isoformat()
    )
    # Os dados de cobrança são pedidos pela página do Asaas, não por nós.
    assert "customerData" not in corpo

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
    assert corpo["items"][0]["value"] == 499.0
    assert "subscription" not in corpo


async def test_so_o_exclusive_mensal_tem_teste(client, sem_plano, asaas_falso):
    user_id, _ = sem_plano
    resp = client.post(
        "/conta/checkout", json=_contratacao(plano="premium"), headers=_auth(user_id)
    )
    assert resp.json()["teste"] is False
    assert (
        asaas_falso.pedidos[0][2]["subscription"]["nextDueDate"] == hoje_do_vendedor().isoformat()
    )


@pytest.mark.parametrize("valor", [None, "", "0", "true"])
async def test_vendas_fechadas_nao_abrem_checkout_nem_gravam_aceite(
    client, pg_pool, sem_plano, asaas_falso, monkeypatch, valor
):
    # Só "1" abre: variável ausente ou escrita de outro jeito deixa fechado.
    if valor is None:
        monkeypatch.delenv("VENDAS_ABERTAS")
    else:
        monkeypatch.setenv("VENDAS_ABERTAS", valor)
    user_id, seller_id = sem_plano

    resp = client.post("/conta/checkout", json=_contratacao(), headers=_auth(user_id))

    assert resp.status_code == 503
    assert resp.json()["detail"]["codigo"] == "vendas-fechadas"
    assert asaas_falso.pedidos == []
    async with pg_pool.acquire() as conn:
        aceites = await conn.fetchval(
            "SELECT count(*) FROM aceites_de_termos WHERE seller_id = $1", seller_id
        )
    assert aceites == 0


async def test_a_conta_diz_se_as_vendas_estao_abertas(client, sem_plano, monkeypatch):
    user_id, _ = sem_plano
    monkeypatch.delenv("VENDAS_ABERTAS", raising=False)
    assert client.get("/conta/acesso", headers=_auth(user_id)).json()["vendas_abertas"] is False
    monkeypatch.setenv("VENDAS_ABERTAS", "1")
    assert client.get("/conta/acesso", headers=_auth(user_id)).json()["vendas_abertas"] is True


async def test_com_vendas_fechadas_quem_ja_assina_ainda_cancela(
    client, pg_pool, sem_plano, asaas_falso, monkeypatch
):
    # Fechar as vendas não pode prender ninguém numa cobrança.
    user_id, seller_id = sem_plano
    await _assinante(pg_pool, seller_id)
    monkeypatch.delenv("VENDAS_ABERTAS")

    assert client.post("/conta/cancelar", headers=_auth(user_id)).status_code == 200
    assert any(metodo == "DELETE" for metodo, *_ in asaas_falso.pedidos)


async def test_contratar_com_versao_velha_dos_termos_nao_abre_checkout(
    client, sem_plano, asaas_falso
):
    user_id, _ = sem_plano
    resp = client.post(
        "/conta/checkout", json=_contratacao(versao_dos_termos="velha"), headers=_auth(user_id)
    )
    assert resp.status_code == 409
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


# Os avisos abaixo seguem o formato REAL, medido no sandbox (2026-10-29): o
# `CHECKOUT_PAID` traz `customer: null` e `subscription` com a CONFIGURAÇÃO da
# assinatura; o pagamento e a assinatura trazem `checkoutSession`, o id do
# checkout que criamos.


def _checkout_pago(evento_id="evt_chk", checkout_id="chk_1"):
    return {
        "id": evento_id,
        "event": "CHECKOUT_PAID",
        "checkout": {
            "id": checkout_id,
            "customer": None,
            "status": "PAID",
            "subscription": {
                "cycle": "MONTHLY",
                "endDate": None,
                "nextDueDate": "2026-11-09T03:00:00+0000",
            },
            # Caso o Asaas repita dado pessoal: não pode ser gravado.
            "customerData": {"name": "Loja", "cpfCnpj": "12345678909", "email": "a@b.dev"},
            "externalReference": "seller:x",
        },
    }


def _assinatura_criada(evento_id="evt_sub", assinatura="sub_1", cliente="cus_1", checkout="chk_1"):
    return {
        "id": evento_id,
        "event": "SUBSCRIPTION_CREATED",
        "subscription": {
            "id": assinatura,
            "customer": cliente,
            "cycle": "MONTHLY",
            "status": "ACTIVE",
            "checkoutSession": checkout,
        },
    }


def _pagamento(
    evento_id,
    vencimento: date,
    tipo="PAYMENT_CONFIRMED",
    assinatura="sub_1",
    checkout="chk_1",
    cliente="cus_1",
):
    return {
        "id": evento_id,
        "event": tipo,
        "payment": {
            "id": f"pay_{evento_id}",
            "customer": cliente,
            "subscription": assinatura,
            "checkoutSession": checkout,
            "dueDate": vencimento.isoformat(),
            "status": "CONFIRMED",
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
    # O checkout pago não traz cliente nem assinatura: chegam nos outros avisos.
    assert (linha["asaas_cliente"], linha["asaas_assinatura"]) == (None, None)
    assert linha["checkout_id"] == "chk_1"
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
    await eventos.processa(pg_pool, _assinatura_criada())
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
    assert asaas_falso.pedidos == [("PUT", "/v3/subscriptions/sub_9", {"value": 139.9})]
    assert (await _assinatura(pg_pool, seller_id))["plano"] == "premium"


async def test_downgrade_fica_para_o_proximo_ciclo(client, pg_pool, test_seller, asaas_falso):
    user_id, seller_id = test_seller
    await _assinante(pg_pool, seller_id, "premium")
    resp = client.post("/conta/plano", json={"plano": "essencial"}, headers=_auth(user_id))
    assert resp.json() == {"plano": "premium", "no_proximo_ciclo": "essencial"}
    assert asaas_falso.pedidos == [("PUT", "/v3/subscriptions/sub_9", {"value": 49.9})]
    linha = await _assinatura(pg_pool, seller_id)
    assert (linha["plano"], linha["plano_no_proximo_ciclo"]) == ("premium", "essencial")


async def test_trocar_plano_dado_a_mao_e_recusado(client, test_seller, asaas_falso):
    user_id, _ = test_seller
    resp = client.post("/conta/plano", json={"plano": "premium"}, headers=_auth(user_id))
    assert resp.status_code == 409
    assert asaas_falso.pedidos == []


async def test_quem_nao_aceitou_a_versao_nova_consegue_cancelar(
    client, pg_pool, test_seller, asaas_falso
):
    # Os Termos prometem esta saída na tela de aceite, onde o painel ainda está bloqueado.
    user_id, seller_id = test_seller
    await _assinante(pg_pool, seller_id)
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM aceites_de_termos WHERE seller_id = $1", seller_id)
    recusa = client.post("/conta/plano", json={"plano": "premium"}, headers=_auth(user_id))
    assert recusa.status_code == 403
    resp = client.post("/conta/cancelar", headers=_auth(user_id))
    assert resp.status_code == 200
    assert asaas_falso.pedidos == [("DELETE", "/v3/subscriptions/sub_9", None)]


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


# ---------- correções da revisão ----------


async def test_o_primeiro_pagamento_grava_o_id_da_assinatura(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    await eventos.processa(pg_pool, _pagamento("evt_p1", HOJE + timedelta(days=7)))
    assert (await _assinatura(pg_pool, seller_id))["asaas_assinatura"] == "sub_1"


async def test_subscription_created_liga_a_assinatura_pelo_cliente(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    assert await eventos.processa(pg_pool, _assinatura_criada()) == "assinatura-ligada"
    assert (await _assinatura(pg_pool, seller_id))["asaas_assinatura"] == "sub_1"


async def test_na_ordem_real_do_sandbox_o_pagamento_ativa_e_o_checkout_pago_nao_reativa(
    pg_pool, sem_plano
):
    """A ordem medida no sandbox: pagamento, assinatura criada, e só então o
    checkout pago. O pagamento de um checkout nosso já prova a compra."""
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id, plano="essencial")

    assert (
        await eventos.processa(pg_pool, _pagamento("evt_p0", HOJE), hoje=HOJE) == "prazo-estendido"
    )
    assert await eventos.processa(pg_pool, _assinatura_criada()) == "assinatura-ligada"
    assert await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE) == "ja-ativado"

    linha = await _assinatura(pg_pool, seller_id)
    assert (linha["plano"], linha["origem"]) == ("essencial", "gateway")
    assert (linha["asaas_cliente"], linha["asaas_assinatura"]) == ("cus_1", "sub_1")
    assert linha["pago_ate"] == meia_noite_do_vendedor(fim_do_periodo(HOJE, "mensal"))


async def test_renovacao_com_o_mesmo_checkout_nao_desfaz_o_downgrade(pg_pool, sem_plano):
    """As renovações também trazem o checkout: não podem reativar o plano comprado."""
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id, plano="premium")
    await eventos.processa(pg_pool, _pagamento("evt_p1", HOJE), hoje=HOJE)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET plano_no_proximo_ciclo = 'essencial' WHERE seller_id = $1",
            seller_id,
        )

    proximo = fim_do_periodo(HOJE, "mensal")
    await eventos.processa(pg_pool, _pagamento("evt_p2", proximo), hoje=proximo)

    linha = await _assinatura(pg_pool, seller_id)
    assert (linha["plano"], linha["plano_no_proximo_ciclo"]) == ("essencial", None)


async def test_cancelar_no_teste_descobre_a_assinatura_no_asaas(
    client, pg_pool, sem_plano, asaas_falso
):
    """No teste de 7 dias nenhum pagamento trouxe o id da assinatura, e o aviso
    de assinatura criada se perdeu: com o cliente conhecido, pergunta ao Asaas."""
    user_id, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=hoje_do_vendedor())
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO aceites_de_termos (seller_id, versao) VALUES ($1, $2)",
            seller_id,
            VERSAO_DOS_TERMOS,
        )
        await conn.execute(
            "UPDATE assinaturas SET asaas_cliente = 'cus_1' WHERE seller_id = $1", seller_id
        )

    resp = client.post("/conta/cancelar", headers=_auth(user_id))

    assert resp.status_code == 200
    assert ("DELETE", "/v3/subscriptions/sub_api", None) in asaas_falso.pedidos
    linha = await _assinatura(pg_pool, seller_id)
    assert linha["cancelada_em"] is not None
    assert linha["acesso_ate"] == linha["pago_ate"]


async def test_cancelar_no_teste_usa_a_assinatura_ligada_pelo_aviso(
    client, pg_pool, sem_plano, asaas_falso
):
    """O caminho real do teste de 7 dias: o aviso de assinatura criada liga o id."""
    user_id, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=hoje_do_vendedor())
    await eventos.processa(pg_pool, _assinatura_criada())
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO aceites_de_termos (seller_id, versao) VALUES ($1, $2)",
            seller_id,
            VERSAO_DOS_TERMOS,
        )

    resp = client.post("/conta/cancelar", headers=_auth(user_id))

    assert resp.status_code == 200
    assert asaas_falso.pedidos == [("DELETE", "/v3/subscriptions/sub_1", None)]


async def test_inadimplente_consegue_cancelar(client, pg_pool, test_seller, asaas_falso):
    user_id, seller_id = test_seller
    await _assinante(pg_pool, seller_id)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET acesso_ate = now() - interval '1 day' WHERE seller_id = $1",
            seller_id,
        )
    resp = client.post("/conta/cancelar", headers=_auth(user_id))
    assert resp.status_code == 200
    assert asaas_falso.pedidos == [("DELETE", "/v3/subscriptions/sub_9", None)]


async def test_recontratar_encerra_a_assinatura_antiga_antes(
    client, pg_pool, test_seller, asaas_falso
):
    """Inadimplente que assina de novo não pode ficar com duas cobranças."""
    user_id, seller_id = test_seller
    await _assinante(pg_pool, seller_id)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET acesso_ate = now() - interval '1 day' WHERE seller_id = $1",
            seller_id,
        )

    resp = client.post("/conta/checkout", json=_contratacao(), headers=_auth(user_id))

    assert resp.status_code == 201
    metodos = [(m, c) for m, c, _ in asaas_falso.pedidos]
    assert metodos[:2] == [("DELETE", "/v3/subscriptions/sub_9"), ("POST", "/v3/checkouts")]
    assert (await _assinatura(pg_pool, seller_id))["cancelada_em"] is not None


async def test_recontratar_nao_abre_checkout_se_o_asaas_nao_encerrar_a_antiga(
    client, pg_pool, test_seller, asaas_falso
):
    user_id, seller_id = test_seller
    await _assinante(pg_pool, seller_id)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET acesso_ate = now() - interval '1 day' WHERE seller_id = $1",
            seller_id,
        )
    asaas_falso.status = 500
    resp = client.post("/conta/checkout", json=_contratacao(), headers=_auth(user_id))
    assert resp.status_code == 502
    assert all(c != "/v3/checkouts" for _, c, _ in asaas_falso.pedidos)


async def test_checkout_novo_depois_de_recontratar_zera_a_assinatura_antiga(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    await eventos.processa(pg_pool, _assinatura_criada())
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET cancelada_em = now() WHERE seller_id = $1", seller_id
        )
    await _checkout_criado(pg_pool, seller_id, checkout_id="chk_2")

    await eventos.processa(
        pg_pool, _checkout_pago(evento_id="evt_chk2", checkout_id="chk_2"), hoje=HOJE
    )

    linha = await _assinatura(pg_pool, seller_id)
    assert (linha["asaas_assinatura"], linha["cancelada_em"]) == (None, None)


async def test_desfazer_um_downgrade_agendado(client, pg_pool, test_seller, asaas_falso):
    user_id, seller_id = test_seller
    await _assinante(pg_pool, seller_id, "premium")
    client.post("/conta/plano", json={"plano": "essencial"}, headers=_auth(user_id))

    resp = client.post("/conta/plano", json={"plano": "premium"}, headers=_auth(user_id))

    assert resp.json() == {"plano": "premium", "no_proximo_ciclo": None}
    assert asaas_falso.pedidos[-1] == ("PUT", "/v3/subscriptions/sub_9", {"value": 139.9})
    assert (await _assinatura(pg_pool, seller_id))["plano_no_proximo_ciclo"] is None


async def test_o_payload_guardado_nao_tem_cpf(pg_pool, sem_plano):
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)
    async with pg_pool.acquire() as conn:
        guardado = await conn.fetchval(
            "SELECT payload::text FROM eventos_do_gateway WHERE id = 'evt_chk'"
        )
    assert "12345678909" not in guardado
    assert "customerData" not in guardado
    assert "chk_1" in guardado


async def test_o_item_do_checkout_leva_a_imagem_que_o_asaas_exige(client, sem_plano, asaas_falso):
    user_id, _ = sem_plano
    client.post("/conta/checkout", json=_contratacao(), headers=_auth(user_id))
    item = asaas_falso.pedidos[0][2]["items"][0]
    assert item["imageBase64"].startswith("iVBORw0KGgo")  # assinatura de PNG em base64


async def test_no_teste_de_7_dias_a_assinatura_ja_aparece_como_recorrente(
    client, pg_pool, sem_plano
):
    """Sem o id gravado ainda, o "Cancelar" não pode sumir da tela."""
    user_id, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id)
    await eventos.processa(pg_pool, _checkout_pago(), hoje=hoje_do_vendedor())
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO aceites_de_termos (seller_id, versao) VALUES ($1, $2)",
            seller_id,
            VERSAO_DOS_TERMOS,
        )
    assinatura = client.get("/conta/acesso", headers=_auth(user_id)).json()["assinatura"]
    assert assinatura["recorrente"] is True


async def test_pagamento_atrasado_da_assinatura_antiga_nao_grava_o_id_antigo(pg_pool, sem_plano):
    """Recontratação: a assinatura antiga (chk_velho / sub_velha) foi cancelada,
    a nova (chk_2) foi paga, e um `PAYMENT_RECEIVED` atrasado da antiga chega
    depois. Ele não pode gravar `sub_velha` na linha da assinatura nova."""
    _, seller_id = sem_plano
    hoje = hoje_do_vendedor()
    velho = hoje - timedelta(days=32)
    await _checkout_criado(pg_pool, seller_id, plano="essencial", checkout_id="chk_velho")
    await eventos.processa(
        pg_pool, _checkout_pago(evento_id="evt_chk_velho", checkout_id="chk_velho"), hoje=velho
    )
    await eventos.processa(
        pg_pool,
        _assinatura_criada(evento_id="evt_sub_velha", assinatura="sub_velha", checkout="chk_velho"),
    )
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET cancelada_em = now() WHERE seller_id = $1", seller_id
        )
    await _checkout_criado(pg_pool, seller_id, plano="essencial", checkout_id="chk_2")
    await eventos.processa(
        pg_pool, _checkout_pago(evento_id="evt_chk_2", checkout_id="chk_2"), hoje=hoje
    )
    # O Asaas reaproveita o cliente da mesma pessoa: a linha nova já o conhece,
    # mas ainda não sabe o id da assinatura nova.
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET asaas_cliente = 'cus_1' WHERE seller_id = $1", seller_id
        )

    antigo = _pagamento(
        "evt_velho", velho, tipo="PAYMENT_RECEIVED", assinatura="sub_velha", checkout="chk_velho"
    )
    assert await eventos.processa(pg_pool, antigo) == "prazo-estendido"

    linha = await _assinatura(pg_pool, seller_id)
    assert (linha["checkout_id"], linha["asaas_assinatura"]) == ("chk_2", None)

    novo = _pagamento("evt_novo", hoje, assinatura="sub_nova", checkout="chk_2")
    await eventos.processa(pg_pool, novo, hoje=hoje)
    assert (await _assinatura(pg_pool, seller_id))["asaas_assinatura"] == "sub_nova"


async def test_segundo_checkout_pago_nao_sobrescreve_o_plano_vigente(pg_pool, sem_plano):
    """Duas abas, dois checkouts, os dois pagos: o segundo não troca os ids da
    assinatura vigente (senão ela seguiria cobrando sem poder ser cancelada)."""
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id, plano="premium", checkout_id="chk_a")
    await _checkout_criado(pg_pool, seller_id, plano="essencial", checkout_id="chk_b")
    await eventos.processa(
        pg_pool, _pagamento("evt_a", HOJE, assinatura="sub_a", checkout="chk_a"), hoje=HOJE
    )

    resultado = await eventos.processa(
        pg_pool, _checkout_pago(evento_id="evt_b", checkout_id="chk_b"), hoje=HOJE
    )

    assert resultado == "checkout-duplicado"
    linha = await _assinatura(pg_pool, seller_id)
    assert (linha["plano"], linha["checkout_id"], linha["asaas_assinatura"]) == (
        "premium",
        "chk_a",
        "sub_a",
    )


def test_base_url_vazia_no_env_vale_como_sandbox(monkeypatch):
    """O `.env` traz `ASAAS_BASE_URL=` vazio; vazio não pode virar URL vazia."""
    monkeypatch.setenv("ASAAS_API_KEY", "chave-de-teste")
    monkeypatch.setenv("ASAAS_BASE_URL", "")
    assert str(asaas._cliente().base_url) == asaas.URL_PADRAO + "/"


async def test_asaas_fora_do_ar_vira_502_e_nao_500(client, monkeypatch, sem_plano):
    def sem_rede(request):
        raise httpx.ConnectError("sem rede", request=request)

    monkeypatch.setenv("ASAAS_API_KEY", "chave-de-teste")
    monkeypatch.setenv("VENDAS_ABERTAS", "1")
    monkeypatch.setattr(
        asaas,
        "_cliente",
        lambda: httpx.AsyncClient(
            base_url="https://asaas.test/v3", transport=httpx.MockTransport(sem_rede)
        ),
    )
    user_id, _ = sem_plano
    resp = client.post("/conta/checkout", json=_contratacao(), headers=_auth(user_id))
    assert resp.status_code == 502
    assert resp.json()["detail"]["codigo"] == "gateway-recusou"


async def test_o_checkout_nao_recebe_nem_manda_dado_de_cliente(client, sem_plano, asaas_falso):
    """Nome, CPF/CNPJ, e-mail e endereço ficam na página do Asaas.

    Mandar `customerData` faz o Asaas exigir endereço completo e telefone
    (medido no sandbox); sem ele, a página dele coleta. Um corpo com esses
    campos é ignorado, não repassado.
    """
    user_id, _ = sem_plano
    resp = client.post(
        "/conta/checkout",
        json=_contratacao(nome="Loja", cpf_cnpj="52998224725", email="a@b.dev"),
        headers=_auth(user_id),
    )
    assert resp.status_code == 201
    corpo = asaas_falso.pedidos[0][2]
    assert "customerData" not in corpo
    assert "52998224725" not in json.dumps(corpo)


async def test_estorno_acha_o_vendedor_pelo_checkout_quando_os_ids_nao_chegaram(pg_pool, sem_plano):
    """Só o checkout pago chegou (sem cliente nem assinatura); o estorno traz o checkout."""
    _, seller_id = sem_plano
    await _checkout_criado(pg_pool, seller_id, plano="premium", ciclo="anual")
    await eventos.processa(pg_pool, _checkout_pago(), hoje=HOJE)

    estorno = _pagamento("evt_r", HOJE, tipo="PAYMENT_REFUNDED", assinatura=None, cliente=None)
    assert await eventos.processa(pg_pool, estorno) == "acesso-encurtado"

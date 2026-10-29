# backend/routers/conta.py
"""O que o vendedor pode acessar, o aceite dos termos e a assinatura.

`GET /conta/acesso` é o que o layout do painel pergunta antes de desenhar
qualquer tela: sem plano vai para /planos, sem aceite para /aceite, e com os
dois desenha o painel com os cadeados do plano. Responde sem exigir plano,
porque é justamente quem não tem que precisa saber disso.

Contratar, trocar e cancelar falam com o Asaas (`backend/pagamentos/`).

Desenho em docs/specs/2026-10-28-planos-e-acesso-design.md e
docs/specs/2026-10-29-cobranca-asaas-design.md.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from backend.db import get_pool
from backend.deps import Acesso, get_acesso, get_current_seller_id, le_plano_e_aceite, recusa
from backend.pagamentos import asaas
from backend.pagamentos.eventos import referencia_do_vendedor
from backend.pagamentos.prazos import hoje_do_vendedor
from backend.planos import DIAS_DE_TESTE, PLANOS, PLANOS_COM_TESTE, VERSAO_DOS_TERMOS

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/conta", tags=["conta"])

# Teto do que se grava do navegador. O valor vem do cliente e vai para o banco
# como prova; não tem por que aceitar um texto de tamanho arbitrário.
_MAX_USER_AGENT = 512
_MAX_IP = 256

NomeDoPlano = Literal["essencial", "exclusive", "premium"]


@router.get("/acesso")
async def get_acesso_da_conta(seller_id: uuid.UUID = Depends(get_current_seller_id)) -> dict:
    pool = await get_pool()
    plano, aceitou = await le_plano_e_aceite(pool, seller_id)
    async with pool.acquire() as conn:
        assinatura = await conn.fetchrow(
            """
            SELECT origem, ciclo, pago_ate, acesso_ate, plano_no_proximo_ciclo,
                   cancelada_em IS NOT NULL AS cancelada,
                   -- Mensal pelo Asaas e não cancelado: tem o que trocar e cancelar,
                   -- MESMO sem o id gravado (no teste de 7 dias ele ainda não
                   -- chegou; `_id_da_assinatura` pergunta ao Asaas). Depender do id
                   -- escondia o "Cancelar" de quem estava no teste.
                   origem = 'gateway' AND ciclo = 'mensal' AND cancelada_em IS NULL
                       AS recorrente
              FROM assinaturas WHERE seller_id = $1
            """,
            seller_id,
        )
    return {
        "plano": plano.nome if plano else None,
        "recursos": sorted(plano.recursos) if plano else [],
        "dias_de_historico": plano.dias_de_historico if plano else None,
        "produtos_na_abc": plano.produtos_na_abc if plano else None,
        "termos": {"versao": VERSAO_DOS_TERMOS, "aceito": aceitou},
        # O que a tela "Minha assinatura" mostra. Vem mesmo com o plano vencido:
        # é ali que o vendedor descobre por que perdeu o acesso.
        "assinatura": None
        if assinatura is None
        else {
            "origem": assinatura["origem"],
            "ciclo": assinatura["ciclo"],
            "pago_ate": _iso(assinatura["pago_ate"]),
            "acesso_ate": _iso(assinatura["acesso_ate"]),
            "plano_no_proximo_ciclo": assinatura["plano_no_proximo_ciclo"],
            "recorrente": assinatura["recorrente"],
            "cancelada": assinatura["cancelada"],
        },
    }


def _iso(valor) -> str | None:
    return valor.isoformat() if valor else None


class Aceite(BaseModel):
    # O front manda a versão que MOSTROU. Se ela não for a vigente (aba aberta
    # antes de os termos mudarem), o aceite é recusado: aceitar um texto que
    # não é o que vale não prova nada.
    versao: str


def _ip_de(request: Request) -> str | None:
    # No Render a requisição chega por proxy, e o socket é o do proxy. Guarda
    # a cadeia inteira do X-Forwarded-For, e não só o primeiro: o primeiro
    # pode ter vindo do próprio cliente, e para prova vale mais a cadeia
    # completa do que um palpite sobre qual elo é o verdadeiro.
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado[:_MAX_IP]
    return request.client.host if request.client else None


async def _grava_aceite(pool, seller_id: uuid.UUID, versao: str, request: Request) -> None:
    if versao != VERSAO_DOS_TERMOS:
        raise recusa(409, "versao-desatualizada", "Os termos mudaram; recarregue a página")
    user_agent = (request.headers.get("user-agent") or "")[:_MAX_USER_AGENT] or None
    async with pool.acquire() as conn:
        # Aceitar de novo a mesma versão não duplica a prova: vale o primeiro.
        await conn.execute(
            """
            INSERT INTO aceites_de_termos (seller_id, versao, ip, user_agent)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (seller_id, versao) DO NOTHING
            """,
            seller_id,
            VERSAO_DOS_TERMOS,
            _ip_de(request),
            user_agent,
        )


@router.post("/aceite", status_code=201)
async def post_aceite(
    corpo: Aceite,
    request: Request,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> dict:
    """Aceite de quem já tem plano (o dado à mão, ou a versão nova dos termos).

    Quem contrata pelo checkout aceita lá, antes de pagar (`/conta/checkout`).
    """
    pool = await get_pool()
    plano, _ = await le_plano_e_aceite(pool, seller_id)
    # Sem plano não há contrato para aceitar (decisão 1 da spec de planos).
    if plano is None:
        raise recusa(402, "sem-plano", "Contrate um plano antes de aceitar os termos")
    await _grava_aceite(pool, seller_id, corpo.versao, request)
    return {"versao": VERSAO_DOS_TERMOS, "aceito": True}


# ---------- contratar ----------


class Contratacao(BaseModel):
    plano: NomeDoPlano
    ciclo: Literal["mensal", "anual"]
    versao_dos_termos: str
    nome: str = Field(min_length=3, max_length=120)
    cpf_cnpj: str = Field(min_length=11, max_length=18)
    # Conferência leve: o Asaas valida de novo, e uma dependência a mais só
    # para isso não se paga.
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _cpf_cnpj_normalizado(valor: str) -> str:
    """CPF com 11 dígitos, ou CNPJ com 14 caracteres.

    O CNPJ pode ter letras nas 12 primeiras posições: a Receita emite o CNPJ
    alfanumérico desde julho de 2026, e só os 2 dígitos verificadores
    continuam numéricos. Tirar as letras recusaria toda empresa nova.
    """
    limpo = re.sub(r"[^0-9A-Za-z]", "", valor).upper()
    cpf = len(limpo) == 11 and limpo.isdigit()
    cnpj = len(limpo) == 14 and limpo[-2:].isdigit()
    if not (cpf or cnpj):
        raise recusa(
            422, "cpf-cnpj-invalido", "Informe um CPF (11 dígitos) ou um CNPJ (14 caracteres)"
        )
    return limpo


def _url_de_retorno() -> str:
    # Fora do /dashboard de propósito: quem volta do pagamento ainda não tem
    # plano (ele chega pelo webhook, segundos depois), e o layout do painel o
    # mandaria para /planos. A página de retorno espera o plano aparecer.
    return f"{os.environ['FRONTEND_URL'].rstrip('/')}/assinar/retorno"


@router.post("/checkout", status_code=201)
async def post_checkout(
    corpo: Contratacao,
    request: Request,
    seller_id: uuid.UUID = Depends(get_current_seller_id),
) -> dict:
    """Aceite dos termos, depois o checkout do Asaas. Devolve o link para pagar.

    O aceite vem ANTES do pagamento (decisão 2 da spec de cobrança). O valor
    sai de `backend/planos.py`, nunca do corpo. O CPF/CNPJ vai para o Asaas e
    não é guardado aqui.
    """
    if not asaas.configurado():
        raise recusa(503, "cobranca-indisponivel", "A contratação está indisponível agora")
    cpf_cnpj = _cpf_cnpj_normalizado(corpo.cpf_cnpj)
    pool = await get_pool()

    plano_atual, _ = await le_plano_e_aceite(pool, seller_id)
    if plano_atual is not None:
        # Quem já tem plano troca por /conta/plano: um segundo checkout criaria
        # uma segunda assinatura cobrando em paralelo.
        raise recusa(409, "ja-tem-plano", "Você já tem um plano; troque pela sua assinatura")

    await _grava_aceite(pool, seller_id, corpo.versao_dos_termos, request)

    # Quem volta depois de ficar inadimplente ainda tem a assinatura antiga
    # viva no Asaas, gerando cobrança todo mês. Encerra ANTES do checkout novo:
    # duas assinaturas cobrando em paralelo é exatamente o que não pode existir.
    # Se o Asaas recusar, não abre o checkout novo.
    await _encerra_assinatura_anterior(pool, seller_id)

    plano = PLANOS[corpo.plano]
    recorrente = corpo.ciclo == "mensal"
    teste = recorrente and corpo.plano in PLANOS_COM_TESTE
    try:
        checkout = await asaas.criar_checkout(
            nome_do_item=f"SellerPulse {corpo.plano.capitalize()}",
            valor=plano.preco(corpo.ciclo),
            ciclo=corpo.ciclo,
            recorrente=recorrente,
            primeira_cobranca=hoje_do_vendedor() + timedelta(days=DIAS_DE_TESTE if teste else 0),
            cliente={"name": corpo.nome, "cpfCnpj": cpf_cnpj, "email": corpo.email},
            referencia=referencia_do_vendedor(seller_id),
            url_de_retorno=_url_de_retorno(),
        )
    except asaas.AsaasErro as erro:
        _log.error("[asaas] checkout recusado: %s", erro)
        raise recusa(502, "gateway-recusou", "Não foi possível abrir o pagamento agora") from erro

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO checkouts (id, seller_id, plano, ciclo) VALUES ($1, $2, $3, $4)",
            checkout["id"],
            seller_id,
            corpo.plano,
            corpo.ciclo,
        )
    return {"link": checkout["link"], "teste": teste}


# ---------- trocar e cancelar ----------


class Troca(BaseModel):
    plano: NomeDoPlano


async def _id_da_assinatura(pool, seller_id: uuid.UUID):
    """`(linha, id da assinatura no Asaas)` de uma assinatura mensal não cancelada.

    O id pode ainda não estar gravado: o checkout pago não o traz, e no teste
    de 7 dias nenhum pagamento chegou para trazê-lo. Aí pergunta ao Asaas pelo
    cliente, e grava. `(linha, None)` quando não há o que mexer (plano dado à
    mão, anual, ou já cancelado).
    """
    async with pool.acquire() as conn:
        linha = await conn.fetchrow(
            "SELECT plano, ciclo, origem, asaas_cliente, asaas_assinatura, pago_ate, "
            "cancelada_em, plano_no_proximo_ciclo FROM assinaturas WHERE seller_id = $1",
            seller_id,
        )
    if (
        linha is None
        or linha["origem"] != "gateway"
        or linha["ciclo"] != "mensal"
        or linha["cancelada_em"] is not None
    ):
        return linha, None
    if linha["asaas_assinatura"]:
        return linha, linha["asaas_assinatura"]
    if not linha["asaas_cliente"]:
        return linha, None
    try:
        ativas = await asaas.assinaturas_ativas_do_cliente(linha["asaas_cliente"])
    except asaas.AsaasErro as erro:
        _log.error("[asaas] consulta de assinaturas recusada: %s", erro)
        raise recusa(
            502, "gateway-recusou", "Não foi possível consultar a assinatura agora"
        ) from erro
    if not ativas:
        return linha, None
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET asaas_assinatura = $2 "
            "WHERE seller_id = $1 AND asaas_assinatura IS NULL",
            seller_id,
            ativas[0],
        )
    return linha, ativas[0]


async def _assinatura_recorrente(pool, seller_id: uuid.UUID):
    linha, assinatura = await _id_da_assinatura(pool, seller_id)
    if assinatura is None:
        raise recusa(
            409, "sem-assinatura-recorrente", "Seu plano não tem cobrança mensal para alterar"
        )
    return linha, assinatura


async def _encerra_assinatura_anterior(pool, seller_id: uuid.UUID) -> None:
    _, assinatura = await _id_da_assinatura(pool, seller_id)
    if assinatura is None:
        return
    try:
        await asaas.remover_assinatura(assinatura)
    except asaas.AsaasErro as erro:
        _log.error("[asaas] assinatura anterior nao encerrada: %s", erro)
        raise recusa(502, "gateway-recusou", "Não foi possível abrir o pagamento agora") from erro
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET cancelada_em = now(), "
            "acesso_ate = LEAST(acesso_ate, pago_ate) WHERE seller_id = $1",
            seller_id,
        )


@router.post("/plano")
async def post_troca_de_plano(corpo: Troca, acesso: Acesso = Depends(get_acesso)) -> dict:
    """Upgrade vale na hora; downgrade, no próximo ciclo (decisão 6 da spec).

    Nos dois casos o valor novo vale a partir da próxima cobrança: a diferença
    do mês corrente, no upgrade, fica por nossa conta.
    """
    pool = await get_pool()
    linha, assinatura = await _assinatura_recorrente(pool, acesso.seller_id)
    novo = PLANOS[corpo.plano]
    atual = PLANOS[linha["plano"]]
    if novo.nome == atual.nome and linha["plano_no_proximo_ciclo"] is None:
        raise recusa(409, "mesmo-plano", "Esse já é o seu plano")
    # Escolher o plano atual com um downgrade agendado desfaz o downgrade: o
    # valor volta ao do plano atual, e nada muda no próximo ciclo.

    try:
        await asaas.mudar_valor_da_assinatura(assinatura, novo.preco_mensal)
    except asaas.AsaasErro as erro:
        _log.error("[asaas] troca de plano recusada: %s", erro)
        raise recusa(502, "gateway-recusou", "Não foi possível trocar o plano agora") from erro

    upgrade = novo.preco_mensal >= atual.preco_mensal
    async with pool.acquire() as conn:
        if upgrade:
            await conn.execute(
                "UPDATE assinaturas SET plano = $2, plano_no_proximo_ciclo = NULL "
                "WHERE seller_id = $1",
                acesso.seller_id,
                novo.nome,
            )
        else:
            await conn.execute(
                "UPDATE assinaturas SET plano_no_proximo_ciclo = $2 WHERE seller_id = $1",
                acesso.seller_id,
                novo.nome,
            )
    return {
        "plano": novo.nome if upgrade else atual.nome,
        "no_proximo_ciclo": None if upgrade else novo.nome,
    }


@router.post("/cancelar")
async def post_cancelar(seller_id: uuid.UUID = Depends(get_current_seller_id)) -> dict:
    """Encerra a recorrência. O acesso vale até o fim do período já pago.

    Não exige plano ativo nem os termos vigentes: o inadimplente, que já
    perdeu o acesso, é justamente quem mais precisa conseguir parar a
    cobrança.
    """
    pool = await get_pool()
    linha, assinatura = await _assinatura_recorrente(pool, seller_id)
    try:
        await asaas.remover_assinatura(assinatura)
    except asaas.AsaasErro as erro:
        _log.error("[asaas] cancelamento recusado: %s", erro)
        raise recusa(502, "gateway-recusou", "Não foi possível cancelar agora") from erro
    async with pool.acquire() as conn:
        # Não espera o webhook: quem cancelou precisa ver o prazo certo já.
        # O `SUBSCRIPTION_DELETED` que vier depois faz a mesma conta.
        await conn.execute(
            "UPDATE assinaturas SET acesso_ate = LEAST(acesso_ate, pago_ate), "
            "plano_no_proximo_ciclo = NULL, cancelada_em = now() WHERE seller_id = $1",
            seller_id,
        )
    return {"acesso_ate": _iso(linha["pago_ate"])}

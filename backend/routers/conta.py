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

import json
import logging
import os
import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel

from backend.db import get_pool
from backend.deps import (
    Acesso,
    get_acesso,
    get_current_seller_id,
    get_current_user_id,
    le_plano_e_aceite,
    recusa,
)
from backend.pagamentos import asaas, avisos
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


def vendas_abertas() -> bool:
    """A contratação nova só abre com `VENDAS_ABERTAS=1`, e nada mais.

    Ausente = fechado, porque o texto final dos termos ainda não existe e o
    checkout cobra de verdade. Lida na hora da chamada: abrir para uma compra de
    teste não exige novo deploy do código. Só trava a contratação nova: cancelar
    e trocar de plano continuam, porque quem assina não pode ficar preso.
    """
    return os.environ.get("VENDAS_ABERTAS") == "1"


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
        "vendas_abertas": vendas_abertas(),
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
    # completa do que um palpite sobre qual elo é o verdadeiro. Se passar do
    # limite, corta o começo: o fim é o elo que o proxy acrescentou, e o começo
    # o cliente escreve como quiser.
    encaminhado = request.headers.get("x-forwarded-for")
    if encaminhado:
        return encaminhado[-_MAX_IP:]
    return request.client.host if request.client else None


@router.post("/registro-de-acesso", status_code=204)
async def post_registro_de_acesso(
    request: Request, user_id: uuid.UUID = Depends(get_current_user_id)
) -> None:
    """Marco Civil, art. 15: data, hora e IP de uso, guardados por 6 meses.

    Quem chama é o navegador, e não o servidor do front: chamado de lá, o IP
    gravado seria o da Vercel. A limpeza acontece aqui porque quem grava é quem
    faz o volume crescer, e assim ela não depende de um agendador. A hora gravada
    é a do começo do período, por isso a folga de uma hora: sem ela, o acesso das
    10:59 sairia antes de completar os 6 meses.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        resultado = await conn.execute(
            """
            INSERT INTO registros_de_acesso (user_id, ip, hora)
            VALUES ($1, $2, date_trunc('hour', now()))
            ON CONFLICT DO NOTHING
            """,
            user_id,
            _ip_de(request) or "desconhecido",
        )
        if resultado == "INSERT 0 1":
            await conn.execute(
                "DELETE FROM registros_de_acesso WHERE hora < now() - interval '6 months 1 hour'"
            )


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
    # Sem nome, CPF/CNPJ, e-mail ou endereço: quem pede os dados de cobrança é
    # a página do Asaas. Com `customerData`, o Asaas exige endereço completo e
    # telefone (medido no sandbox, 2026-10-29); sem ele, a página dele coleta.
    # O SellerPulse não recebe esses dados nem de passagem.


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
    sai de `backend/planos.py`, nunca do corpo. Os dados de cobrança (CPF,
    endereço, cartão) a pessoa preenche na página do Asaas, não aqui.
    """
    # Antes do aceite: com as vendas fechadas, ninguém aceita um texto para
    # contratar algo que não vai acontecer.
    if not vendas_abertas():
        raise recusa(503, "vendas-fechadas", "As vendas ainda não estão abertas")
    if not PLANOS[corpo.plano].a_venda:
        raise recusa(409, "plano-fora-de-venda", "Este plano ainda não está à venda")
    if not asaas.configurado():
        raise recusa(503, "cobranca-indisponivel", "A contratação está indisponível agora")
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


def _mensal_viva(linha) -> bool:
    return (
        linha is not None
        and linha["origem"] == "gateway"
        and linha["ciclo"] == "mensal"
        and linha["cancelada_em"] is None
    )


async def _id_da_assinatura(pool, seller_id: uuid.UUID):
    """`(linha, id da assinatura no Asaas)` de uma assinatura mensal não cancelada.

    O id pode ainda não estar gravado: o checkout pago não o traz, e no teste
    de 7 dias nenhum pagamento chegou para trazê-lo. Aí pergunta ao Asaas pelo
    cliente, e grava. `(linha, None)` quando não há o que mexer (plano dado à
    mão, anual, ou já cancelado).
    """
    async with pool.acquire() as conn:
        linha = await conn.fetchrow(
            "SELECT plano, ciclo, origem, checkout_id, asaas_cliente, asaas_assinatura, pago_ate, "
            "cancelada_em, plano_no_proximo_ciclo FROM assinaturas WHERE seller_id = $1",
            seller_id,
        )
    if not _mensal_viva(linha):
        return linha, None
    if linha["asaas_assinatura"]:
        return linha, linha["asaas_assinatura"]
    if not linha["asaas_cliente"]:
        # Mensal pelo Asaas sem cliente nem assinatura: os avisos que trazem os
        # ids se perderam (fila pausada). Não há como achar a assinatura daqui;
        # o dono precisa cancelar no painel do Asaas.
        _log.warning(
            "[asaas] seller %s mensal sem ids do Asaas (checkout %s): avisos perdidos?",
            seller_id,
            linha["checkout_id"],
        )
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
    # Quem já está no plano pode continuar nele: é o que desfaz um downgrade agendado.
    if not novo.a_venda and novo.nome != atual.nome:
        raise recusa(409, "plano-fora-de-venda", "Este plano ainda não está à venda")
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
    linha, assinatura = await _id_da_assinatura(pool, seller_id)
    if assinatura is not None:
        try:
            await asaas.remover_assinatura(assinatura)
        except asaas.AsaasErro as erro:
            _log.error("[asaas] cancelamento recusado: %s", erro)
            raise recusa(502, "gateway-recusou", "Não foi possível cancelar agora.") from erro
    elif not _mensal_viva(linha):
        raise recusa(
            409, "sem-assinatura-recorrente", "Seu plano não tem cobrança mensal para cancelar."
        )
    elif not linha["asaas_cliente"]:
        # Sem o cliente, daqui não se acha a cobrança, e marcar como cancelado
        # esconderia o botão de uma cobrança que pode continuar viva.
        raise recusa(
            409,
            "assinatura-nao-localizada",
            "Não localizamos a sua assinatura no Asaas, e o cancelamento precisa ser feito por nós.",
        )
    # Com o cliente conhecido e nenhuma assinatura ativa lá, o Asaas já não
    # cobra (o aviso do cancelamento se perdeu): resta encerrar aqui também.
    async with pool.acquire() as conn:
        # Não espera o webhook: quem cancelou precisa ver o prazo certo já.
        # O `SUBSCRIPTION_DELETED` que vier depois faz a mesma conta.
        await conn.execute(
            "UPDATE assinaturas SET acesso_ate = LEAST(acesso_ate, pago_ate), "
            "plano_no_proximo_ciclo = NULL, cancelada_em = now() WHERE seller_id = $1",
            seller_id,
        )
    return {"acesso_ate": _iso(linha["pago_ate"])}


# ---------- desistência (arrependimento de 7 dias) ----------

# CDC, art. 49, e seção 8 dos Termos: 7 dias contados do primeiro pagamento.
DIAS_PARA_DESISTIR = 7
_PAGOS = frozenset({"CONFIRMED", "RECEIVED", "RECEIVED_IN_CASH"})
_ESTORNADOS = frozenset({"REFUNDED", "REFUND_REQUESTED", "REFUND_IN_PROGRESS"})


def _dia_do_pagamento(pagamento: dict) -> date | None:
    # A data mais cedo que o Asaas der: o prazo conta a favor de quem desiste
    # só se não for empurrado para depois do pagamento de verdade.
    dias = [pagamento.get(c) for c in ("confirmedDate", "paymentDate", "clientPaymentDate")]
    validos = [date.fromisoformat(d) for d in dias if d]
    return min(validos) if validos else None


async def _desistencia(pool, seller_id: uuid.UUID):
    """`(linha, pagamentos do contrato, último dia para desistir ou None)`.

    Só os pagamentos do contrato atual: o checkout vigente, ou a assinatura
    vigente. Um cliente que recontratou tem no Asaas os pagamentos dos dois
    contratos, e o pagamento antigo não abre o prazo do novo.
    """
    async with pool.acquire() as conn:
        linha = await conn.fetchrow(
            "SELECT origem, ciclo, checkout_id, asaas_cliente, asaas_assinatura, cancelada_em, "
            "acesso_ate IS NULL OR acesso_ate > now() AS com_acesso "
            "FROM assinaturas WHERE seller_id = $1",
            seller_id,
        )
    if linha is None or linha["origem"] != "gateway" or not linha["asaas_cliente"]:
        return linha, [], None
    try:
        todos = await asaas.pagamentos_do_cliente(linha["asaas_cliente"])
    except asaas.AsaasErro as erro:
        _log.error("[asaas] consulta de pagamentos recusada: %s", erro)
        raise recusa(
            502, "gateway-recusou", "Não foi possível consultar os pagamentos agora."
        ) from erro
    do_contrato = [
        p
        for p in todos
        if (linha["checkout_id"] and p.get("checkoutSession") == linha["checkout_id"])
        or (linha["asaas_assinatura"] and p.get("subscription") == linha["asaas_assinatura"])
    ]
    # O prazo conta do primeiro pagamento, mesmo que ele já tenha sido estornado.
    dias = [d for p in do_contrato if (d := _dia_do_pagamento(p)) is not None]
    if not dias:
        return linha, do_contrato, None
    ultimo = min(dias) + timedelta(days=DIAS_PARA_DESISTIR)
    return linha, do_contrato, ultimo if hoje_do_vendedor() <= ultimo else None


def _o_que_falta(linha, do_contrato: list[dict]) -> tuple[list[dict], list[dict]]:
    """`(a estornar, já estornados que ainda deixam o acesso aberto)`.

    O segundo é a desistência interrompida entre o estorno e o corte (o
    processo caiu): o dinheiro voltou, mas o acesso e a marca contra o aviso
    atrasado não ficaram. A nova tentativa termina o serviço.
    """
    a_estornar = [p for p in do_contrato if p.get("status") in _PAGOS]
    sem_corte = (
        [p for p in do_contrato if p.get("status") in _ESTORNADOS] if linha["com_acesso"] else []
    )
    return a_estornar, sem_corte


@router.get("/pagamentos")
async def get_pagamentos(
    tarefas: BackgroundTasks, seller_id: uuid.UUID = Depends(get_current_seller_id)
) -> dict:
    """Os comprovantes dos pagamentos, lidos do Asaas na hora.

    O link abre a página do Asaas com os dados de quem pagou: por isso nunca é
    guardado (`eventos.sem_dados_pessoais`) e só sai aqui, para a conta dona do
    contrato. Pagamento sem comprovante (pendente, vencido) fica de fora.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        cliente = await conn.fetchval(
            "SELECT asaas_cliente FROM assinaturas WHERE seller_id = $1 AND origem = 'gateway'",
            seller_id,
        )
    if not cliente:
        return {"pagamentos": []}
    # Quem pagou antes de os avisos existirem só é alcançado aqui.
    tarefas.add_task(avisos.garante, pool, cliente)
    try:
        todos = await asaas.pagamentos_do_cliente(cliente)
    except asaas.AsaasErro as erro:
        _log.error("[asaas] consulta de pagamentos recusada: %s", erro)
        raise recusa(
            502, "gateway-recusou", "Não foi possível consultar os pagamentos agora."
        ) from erro
    pagamentos = [
        {
            "dia": dia.isoformat(),
            "valor": p.get("value"),
            "comprovante": p["transactionReceiptUrl"],
            "devolvido": p.get("status") in _ESTORNADOS,
        }
        for p in todos
        # Sem valor, a linha sairia "R$ 0,00": ausência não vira zero.
        if p.get("transactionReceiptUrl")
        and p.get("value") is not None
        and (dia := _dia_do_pagamento(p)) is not None
    ]
    pagamentos.sort(key=lambda p: p["dia"], reverse=True)
    return {"pagamentos": pagamentos}


@router.get("/desistencia")
async def get_desistencia(seller_id: uuid.UUID = Depends(get_current_seller_id)) -> dict:
    """O último dia para desistir com o valor de volta, ou `None` se não há o que desistir.

    `ja_devolvido`: o dinheiro já voltou (desistência interrompida, ou estorno
    feito à mão pelo suporte) e falta só encerrar o acesso. A tela não pode
    prometer um valor que não vem mais.
    """
    linha, do_contrato, ultimo = await _desistencia(await get_pool(), seller_id)
    if ultimo is None:
        return {"ate": None}
    a_estornar, sem_corte = _o_que_falta(linha, do_contrato)
    if not a_estornar and not sem_corte:
        return {"ate": None}
    return {"ate": ultimo.isoformat(), "ja_devolvido": not a_estornar}


@router.post("/desistir")
async def post_desistir(seller_id: uuid.UUID = Depends(get_current_seller_id)) -> dict:
    """Encerra a recorrência, estorna os pagamentos do contrato e corta o acesso.

    Nessa ordem: sem a recorrência encerrada, um estorno feito antes deixaria a
    próxima cobrança viva. O acesso só acaba depois do estorno, porque quem não
    recebeu o dinheiro de volta ainda pagou pelo período.
    """
    pool = await get_pool()
    linha, do_contrato, ultimo = await _desistencia(pool, seller_id)
    if linha is None or linha["origem"] != "gateway":
        raise recusa(409, "sem-assinatura", "Seu plano não tem pagamento para devolver.")
    if ultimo is None:
        raise recusa(
            409,
            "fora-do-prazo",
            "O prazo de 7 dias para desistir já passou. Você ainda pode cancelar a assinatura.",
        )
    a_estornar, sem_corte = _o_que_falta(linha, do_contrato)
    if not a_estornar and not sem_corte:
        raise recusa(409, "ja-devolvido", "Os pagamentos desta assinatura já foram devolvidos.")

    if _mensal_viva(linha):
        _, assinatura = await _id_da_assinatura(pool, seller_id)
        if assinatura is not None:
            try:
                await asaas.remover_assinatura(assinatura)
            except asaas.AsaasErro as erro:
                _log.error("[asaas] desistencia: cancelamento recusado: %s", erro)
                raise recusa(502, "gateway-recusou", "Não foi possível desistir agora.") from erro
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE assinaturas SET cancelada_em = COALESCE(cancelada_em, now()), "
            "acesso_ate = LEAST(acesso_ate, pago_ate), plano_no_proximo_ciclo = NULL "
            "WHERE seller_id = $1",
            seller_id,
        )

    for pagamento in a_estornar:
        try:
            estorno = await asaas.estornar_pagamento(pagamento["id"])
        except asaas.AsaasErro as erro:
            _log.error(
                "[asaas] desistencia: estorno do pagamento %s recusado (seller %s), "
                "estornar no painel do Asaas: %s",
                pagamento["id"],
                seller_id,
                erro,
            )
            raise recusa(
                502,
                "estorno-pendente",
                "A assinatura foi cancelada, mas o estorno não saiu agora. "
                "Já fomos avisados e vamos devolver o valor.",
            ) from erro
        await _marca_desistencia(pool, pagamento["id"], seller_id)
        # Uma conta que exige autorização de ação crítica deixa o estorno parado
        # até o dono aprovar no painel: o status vai para o log.
        _log.warning(
            "[asaas] desistencia: estorno do pagamento %s com status %s",
            pagamento["id"],
            estorno.get("status"),
        )

    for pagamento in sem_corte:
        await _marca_desistencia(pool, pagamento["id"], seller_id)

    async with pool.acquire() as conn:
        # O dinheiro voltou inteiro: não sobra período pago. O `PAYMENT_REFUNDED`
        # que chega depois só encurta (`LEAST`), e não devolve a tolerância.
        await conn.execute(
            "UPDATE assinaturas SET acesso_ate = now(), pago_ate = LEAST(pago_ate, now()) "
            "WHERE seller_id = $1",
            seller_id,
        )
    _log.warning(
        "[asaas] desistencia do seller %s: %d pagamento(s) estornado(s)",
        seller_id,
        len(a_estornar),
    )
    return {"estornados": len(a_estornar)}


async def _marca_desistencia(pool, pagamento: str, seller_id: uuid.UUID) -> None:
    """A marca que impede o aviso atrasado deste pagamento de devolver o acesso
    (`_pagamento_confirmado`). Mora no log de eventos, sem coluna nova."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO eventos_do_gateway (id, tipo, payload) VALUES ($1, $2, $3::jsonb) "
            "ON CONFLICT (id) DO NOTHING",
            f"desistencia:{pagamento}",
            "DESISTENCIA",
            json.dumps({"payment": pagamento, "seller": str(seller_id)}),
        )

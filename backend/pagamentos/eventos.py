# backend/pagamentos/eventos.py
"""O que cada evento do webhook do Asaas faz com o acesso do vendedor.

Regras que valem para todos:

- **Idempotente pelo `id` do evento.** O Asaas entrega "pelo menos uma vez".
  O evento é gravado na MESMA transação em que é aplicado: se aplicar falha,
  nada fica gravado, e o reenvio do Asaas tenta de novo.
- **O checkout é o elo.** Medido no sandbox (2026-10-29): o pagamento e a
  assinatura trazem `checkoutSession` (o id do checkout que criamos), e o
  `CHECKOUT_PAID` traz `customer: null`. E a fila chega FORA DE ORDEM mesmo no
  envio sequencial: o pagamento e a assinatura chegaram antes do checkout pago.
  Por isso todo aviso que traz o checkout anota nele o cliente e a assinatura,
  e o primeiro que prova o pagamento ativa o plano — uma vez só (`pago_em`).
- **O prazo só cresce com pagamento** (`GREATEST`). `PAYMENT_CONFIRMED` e
  `PAYMENT_RECEIVED` chegam os dois para a mesma cobrança, às vezes com 32
  dias de diferença (cartão). Nenhum deles pode encurtar o que o outro deu.
- **Evento que não se sabe de quem é não derruba nada.** Vira aviso no log e
  resposta 200: o Asaas pausa a fila depois de 15 falhas seguidas, e uma fila
  pausada atrasa o pagamento de todo mundo.

Desenho em docs/specs/2026-10-29-cobranca-asaas-design.md.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, timedelta

import asyncpg

from backend.pagamentos.prazos import (
    hoje_do_vendedor,
    meia_noite_do_vendedor,
    prazos_de_um_pagamento,
)
from backend.planos import DIAS_DE_TESTE, DIAS_DE_TOLERANCIA, PLANOS_COM_TESTE

_log = logging.getLogger(__name__)

_PAGAMENTO_CONFIRMADO = frozenset({"PAYMENT_CONFIRMED", "PAYMENT_RECEIVED"})
_ASSINATURA_ENCERRADA = frozenset({"SUBSCRIPTION_DELETED", "SUBSCRIPTION_INACTIVATED"})
_DINHEIRO_DEVOLVIDO = frozenset({"PAYMENT_REFUNDED", "PAYMENT_CHARGEBACK_REQUESTED"})

# Dado pessoal de quem paga, que o Asaas pode repetir no payload. Os dados de
# cobrança não são guardados no SellerPulse (spec, "Contratar"), e o log de
# eventos não pode virar a exceção: estas chaves saem antes de gravar.
_CHAVES_PESSOAIS = frozenset(
    {"cpfCnpj", "customerData", "creditCard", "creditCardHolderInfo", "phone", "mobilePhone"}
)


def sem_dados_pessoais(valor):
    """Cópia do payload sem as chaves de dado pessoal, recursivamente."""
    if isinstance(valor, dict):
        return {k: sem_dados_pessoais(v) for k, v in valor.items() if k not in _CHAVES_PESSOAIS}
    if isinstance(valor, list):
        return [sem_dados_pessoais(v) for v in valor]
    return valor


def _id_de(valor) -> str | None:
    """O Asaas manda referência ora como string, ora como objeto com `id`."""
    if isinstance(valor, dict):
        return valor.get("id")
    return valor if isinstance(valor, str) and valor else None


async def processa(pool: asyncpg.Pool, evento: dict, *, hoje: date | None = None) -> str:
    """Aplica o evento e devolve, em uma palavra, o que aconteceu (vai pro log)."""
    hoje = hoje or hoje_do_vendedor()
    id_do_evento = evento.get("id")
    tipo = evento.get("event") or ""
    if not id_do_evento:
        _log.warning("[asaas] evento sem id ignorado: %s", tipo)
        return "sem-id"

    async with pool.acquire() as conn, conn.transaction():
        novo = await conn.fetchval(
            """
            INSERT INTO eventos_do_gateway (id, tipo, payload) VALUES ($1, $2, $3::jsonb)
            ON CONFLICT (id) DO NOTHING RETURNING id
            """,
            id_do_evento,
            tipo,
            json.dumps(sem_dados_pessoais(evento)),
        )
        if novo is None:
            return "repetido"

        if tipo == "CHECKOUT_PAID":
            return await _ativa_checkout(conn, _id_de(evento.get("checkout")), hoje)
        if tipo in _PAGAMENTO_CONFIRMADO:
            return await _pagamento_confirmado(conn, evento.get("payment") or {}, hoje)
        if tipo == "SUBSCRIPTION_CREATED":
            return await _assinatura_criada(conn, evento.get("subscription") or {})
        if tipo in _ASSINATURA_ENCERRADA:
            return await _assinatura_encerrada(conn, evento.get("subscription") or {})
        if tipo in _DINHEIRO_DEVOLVIDO:
            return await _dinheiro_devolvido(conn, evento.get("payment") or {}, tipo)
        return "ignorado"


async def _anota_ids(conn, checkout_id: str, cliente: str | None, assinatura: str | None) -> bool:
    """Anota no checkout (e na assinatura que ele ativou) os ids do Asaas.

    Chamado por qualquer aviso que traga o checkout, na ordem em que chegarem.
    Só preenche o que falta (`COALESCE`). A linha de `assinaturas` só é tocada
    se ela é a deste checkout: um aviso atrasado de um checkout ANTIGO não
    grava o id de uma assinatura que já foi encerrada na assinatura nova.
    Devolve se o checkout é nosso.
    """
    conhecido = await conn.fetchval(
        """
        UPDATE checkouts SET asaas_cliente = COALESCE(asaas_cliente, $2),
                             asaas_assinatura = COALESCE(asaas_assinatura, $3)
         WHERE id = $1 RETURNING true
        """,
        checkout_id,
        cliente,
        assinatura,
    )
    await conn.execute(
        """
        UPDATE assinaturas SET asaas_cliente = COALESCE(asaas_cliente, $2),
                               asaas_assinatura = COALESCE(asaas_assinatura, $3)
         WHERE checkout_id = $1 AND cancelada_em IS NULL
        """,
        checkout_id,
        cliente,
        assinatura,
    )
    return bool(conhecido)


async def _ativa_checkout(conn, checkout_id: str | None, hoje: date) -> str:
    """Ativa o plano comprado por um checkout nosso. Uma vez só por checkout.

    O `pago_em IS NULL` é o que garante o "uma vez": o `CHECKOUT_PAID` e o
    primeiro pagamento ativam, o que chegar antes; o outro, e as renovações
    que também trazem o checkout, não reativam — reativar desfaria um
    downgrade agendado ou um cancelamento.
    """
    registro = await conn.fetchrow(
        """
        UPDATE checkouts SET pago_em = now()
         WHERE id = $1 AND pago_em IS NULL
        RETURNING seller_id, plano, ciclo, asaas_cliente, asaas_assinatura
        """,
        checkout_id,
    )
    if registro is None:
        existe = await conn.fetchval("SELECT true FROM checkouts WHERE id = $1", checkout_id)
        if not existe:
            _log.warning("[asaas] checkout pago que nao foi criado aqui: %s", checkout_id)
            return "checkout-desconhecido"
        return "ja-ativado"

    # O teste de 7 dias: o cartão foi validado e a primeira cobrança é no 8º
    # dia. O período "pago" vai até lá; os pagamentos seguintes empurram.
    em_teste = registro["ciclo"] == "mensal" and registro["plano"] in PLANOS_COM_TESTE
    if em_teste:
        pago_ate = meia_noite_do_vendedor(hoje + timedelta(days=DIAS_DE_TESTE))
        acesso_ate = pago_ate + timedelta(days=DIAS_DE_TOLERANCIA)
    else:
        pago_ate, acesso_ate = prazos_de_um_pagamento(hoje, registro["ciclo"])

    # Numa recontratação, a linha antiga é reaproveitada com a assinatura NOVA:
    # os ids vêm do checkout novo (nulos se ainda não chegaram), nunca os da
    # assinatura anterior, que foi encerrada antes deste checkout.
    await conn.execute(
        """
        INSERT INTO assinaturas (seller_id, plano, origem, ciclo, checkout_id, asaas_cliente,
                                 asaas_assinatura, pago_ate, acesso_ate, desde)
        VALUES ($1, $2, 'gateway', $3, $4, $5, $6, $7, $8, now())
        ON CONFLICT (seller_id) DO UPDATE SET
            plano = EXCLUDED.plano,
            origem = 'gateway',
            ciclo = EXCLUDED.ciclo,
            checkout_id = EXCLUDED.checkout_id,
            asaas_cliente = EXCLUDED.asaas_cliente,
            asaas_assinatura = EXCLUDED.asaas_assinatura,
            pago_ate = GREATEST(assinaturas.pago_ate, EXCLUDED.pago_ate),
            acesso_ate = GREATEST(assinaturas.acesso_ate, EXCLUDED.acesso_ate),
            plano_no_proximo_ciclo = NULL,
            cancelada_em = NULL,
            desde = now()
        """,
        registro["seller_id"],
        registro["plano"],
        registro["ciclo"],
        checkout_id,
        registro["asaas_cliente"],
        registro["asaas_assinatura"],
        pago_ate,
        acesso_ate,
    )
    return "plano-ativado"


async def _assinatura_criada(conn, assinatura: dict) -> str:
    """Liga o id da assinatura ao vendedor, pelo checkout que a criou.

    É o que deixa cancelar durante o teste de 7 dias, antes de qualquer
    pagamento trazer o id.
    """
    checkout_id = assinatura.get("checkoutSession")
    cliente = _id_de(assinatura.get("customer"))
    if checkout_id:
        conhecido = await _anota_ids(conn, checkout_id, cliente, _id_de(assinatura))
        return "assinatura-ligada" if conhecido else "assinatura-sem-dono"
    resultado = await conn.execute(
        """
        UPDATE assinaturas SET asaas_assinatura = $1
         WHERE asaas_cliente = $2 AND asaas_assinatura IS NULL AND cancelada_em IS NULL
        """,
        _id_de(assinatura),
        cliente,
    )
    return "assinatura-ligada" if resultado.endswith(" 1") else "assinatura-sem-dono"


async def _dono(
    conn, assinatura: str | None, checkout_id: str | None, cliente: str | None
) -> asyncpg.Record | None:
    """A linha de `assinaturas` do aviso: pela assinatura, pelo checkout, ou pelo cliente."""
    for coluna, valor in (
        ("asaas_assinatura", assinatura),
        ("checkout_id", checkout_id),
        ("asaas_cliente", cliente),
    ):
        if valor:
            linha = await conn.fetchrow(
                f"SELECT * FROM assinaturas WHERE {coluna} = $1 FOR UPDATE",  # noqa: S608
                valor,
            )
            if linha is not None:
                return linha
    return None


async def _pagamento_confirmado(conn, pagamento: dict, hoje: date) -> str:
    assinatura = _id_de(pagamento.get("subscription"))
    cliente = _id_de(pagamento.get("customer"))
    checkout_id = pagamento.get("checkoutSession")

    # O primeiro pagamento de um checkout nosso prova a compra: anota os ids e
    # ativa o plano, mesmo que o `CHECKOUT_PAID` ainda não tenha chegado.
    if checkout_id and await _anota_ids(conn, checkout_id, cliente, assinatura):
        await _ativa_checkout(conn, checkout_id, hoje)

    linha = await _dono(conn, assinatura, checkout_id, cliente)
    if linha is None:
        _log.warning("[asaas] pagamento %s sem assinatura conhecida", pagamento.get("id"))
        return "pagamento-sem-dono"

    vencimento = date.fromisoformat(pagamento["dueDate"])
    pago_ate, acesso_ate = prazos_de_um_pagamento(vencimento, linha["ciclo"] or "mensal")

    # O downgrade vale no próximo ciclo: aplica quando chega o pagamento de um
    # período NOVO, isto é, que começa onde o pago terminava. O
    # `PAYMENT_RECEIVED` atrasado de um período antigo vence antes disso e
    # não aplica nada.
    periodo_novo = linha["pago_ate"] is None or (
        vencimento >= linha["pago_ate"].astimezone(pago_ate.tzinfo).date() - timedelta(days=1)
    )
    novo_plano = linha["plano_no_proximo_ciclo"] if periodo_novo else None

    # Pagamento sem checkout (ou de assinatura criada fora dele) traz o id da
    # assinatura que faltava: grava, se ainda faltar, se não foi cancelada, e
    # se o pagamento é da assinatura ATUAL. O `PAYMENT_RECEIVED` atrasado (até
    # 32 dias, no cartão) de uma assinatura antiga vence antes do começo da
    # nova, e gravaria o id antigo aqui.
    await conn.execute(
        """
        UPDATE assinaturas SET asaas_assinatura = $2
         WHERE seller_id = $1 AND asaas_assinatura IS NULL AND cancelada_em IS NULL
           AND $2::text IS NOT NULL
           AND $3 >= (desde AT TIME ZONE 'America/Sao_Paulo')::date
        """,
        linha["seller_id"],
        assinatura,
        vencimento,
    )
    await conn.execute(
        """
        UPDATE assinaturas SET
            pago_ate = GREATEST(pago_ate, $2),
            -- Quem cancelou fica com o período pago, sem a tolerância.
            acesso_ate = GREATEST(acesso_ate,
                                  CASE WHEN cancelada_em IS NULL THEN $3 ELSE $2 END),
            plano = COALESCE($4, plano),
            plano_no_proximo_ciclo = CASE WHEN $4::text IS NULL
                                          THEN plano_no_proximo_ciclo END
        WHERE seller_id = $1
        """,
        linha["seller_id"],
        pago_ate,
        acesso_ate,
        novo_plano,
    )
    return "prazo-estendido"


async def _assinatura_encerrada(conn, assinatura: dict) -> str:
    # Cancelou: o acesso vale até o fim do que já foi pago, sem a tolerância
    # (decisão 5 da spec).
    resultado = await conn.execute(
        """
        UPDATE assinaturas SET acesso_ate = LEAST(acesso_ate, pago_ate),
                               cancelada_em = COALESCE(cancelada_em, now())
        WHERE asaas_assinatura = $1
        """,
        _id_de(assinatura),
    )
    return "encerrada" if resultado.endswith(" 1") else "assinatura-desconhecida"


async def _dinheiro_devolvido(conn, pagamento: dict, tipo: str) -> str:
    linha = await _dono(
        conn,
        _id_de(pagamento.get("subscription")),
        pagamento.get("checkoutSession"),
        _id_de(pagamento.get("customer")),
    )
    if linha is None:
        return "pagamento-sem-dono"
    # Estorno ou contestação: o acesso vai até o fim da tolerância a partir de
    # hoje. Não é corte imediato, porque contestação às vezes é engano. O dono
    # precisa olhar: o aviso vai para o log.
    await conn.execute(
        """
        UPDATE assinaturas
           SET acesso_ate = LEAST(acesso_ate, now() + make_interval(days => $2))
         WHERE seller_id = $1
        """,
        linha["seller_id"],
        DIAS_DE_TOLERANCIA,
    )
    _log.warning(
        "[asaas] %s no pagamento %s (seller %s)", tipo, pagamento.get("id"), linha["seller_id"]
    )
    return "acesso-encurtado"


def referencia_do_vendedor(seller_id: uuid.UUID) -> str:
    """O `externalReference` do checkout: o vendedor, para auditoria no painel do Asaas."""
    return f"seller:{seller_id}"

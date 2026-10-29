# backend/pagamentos/eventos.py
"""O que cada evento do webhook do Asaas faz com o acesso do vendedor.

Regras que valem para todos:

- **Idempotente pelo `id` do evento.** O Asaas entrega "pelo menos uma vez".
  O evento é gravado na MESMA transação em que é aplicado: se aplicar falha,
  nada fica gravado, e o reenvio do Asaas tenta de novo.
- **O prazo só cresce com pagamento** (`GREATEST`). `PAYMENT_CONFIRMED` e
  `PAYMENT_RECEIVED` chegam os dois para a mesma cobrança, às vezes com 32
  dias de diferença (cartão), e às vezes fora de ordem. Nenhum deles pode
  encurtar o que o outro já deu.
- **Evento que não se sabe de quem é não derruba nada.** Vira aviso no log e
  resposta 200: o Asaas pausa a fila depois de 15 falhas seguidas, e uma fila
  pausada atrasa o pagamento de todo mundo.

Os formatos de `checkout` e `payment` seguem a documentação. O que ela não
diz (como o checkout pago aponta para a assinatura criada) está na lista "a
confirmar no sandbox" da spec docs/specs/2026-10-29-cobranca-asaas-design.md.
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

# Dado pessoal de quem paga, que o Asaas pode repetir no payload. O CPF/CNPJ
# não é guardado no SellerPulse (spec, "Contratar"), e o log de eventos não
# pode virar a exceção: estas chaves saem antes de gravar, em qualquer nível.
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
            return await _checkout_pago(conn, evento.get("checkout") or {}, hoje)
        if tipo in _PAGAMENTO_CONFIRMADO:
            return await _pagamento_confirmado(conn, evento.get("payment") or {})
        if tipo == "SUBSCRIPTION_CREATED":
            return await _assinatura_criada(conn, evento.get("subscription") or {})
        if tipo in _ASSINATURA_ENCERRADA:
            return await _assinatura_encerrada(conn, evento.get("subscription") or {})
        if tipo in _DINHEIRO_DEVOLVIDO:
            return await _dinheiro_devolvido(conn, evento.get("payment") or {}, tipo)
        return "ignorado"


async def _checkout_pago(conn, checkout: dict, hoje: date) -> str:
    checkout_id = checkout.get("id")
    registro = await conn.fetchrow(
        "UPDATE checkouts SET pago_em = now() WHERE id = $1 RETURNING seller_id, plano, ciclo",
        checkout_id,
    )
    if registro is None:
        _log.warning("[asaas] checkout pago que nao foi criado aqui: %s", checkout_id)
        return "checkout-desconhecido"

    # O teste de 7 dias: o cartão foi validado e a primeira cobrança é no 8º
    # dia. O período "pago" vai até lá; os pagamentos seguintes empurram.
    em_teste = registro["ciclo"] == "mensal" and registro["plano"] in PLANOS_COM_TESTE
    if em_teste:
        pago_ate = meia_noite_do_vendedor(hoje + timedelta(days=DIAS_DE_TESTE))
        acesso_ate = pago_ate + timedelta(days=DIAS_DE_TOLERANCIA)
    else:
        pago_ate, acesso_ate = prazos_de_um_pagamento(hoje, registro["ciclo"])

    # O `subscription` do checkout é a CONFIGURAÇÃO da assinatura (ciclo,
    # vencimento), não ela: a documentação do evento mostra
    # `{"cycle": ..., "nextDueDate": ...}`. O id chega depois, no
    # `SUBSCRIPTION_CREATED` ou no primeiro pagamento. Por isso
    # `asaas_assinatura` começa nulo — e zera numa recontratação, porque a
    # assinatura anterior foi encerrada antes do checkout novo.
    await conn.execute(
        """
        INSERT INTO assinaturas (seller_id, plano, origem, ciclo, asaas_cliente,
                                 pago_ate, acesso_ate, desde)
        VALUES ($1, $2, 'gateway', $3, $4, $5, $6, now())
        ON CONFLICT (seller_id) DO UPDATE SET
            plano = EXCLUDED.plano,
            origem = 'gateway',
            ciclo = EXCLUDED.ciclo,
            asaas_cliente = COALESCE(EXCLUDED.asaas_cliente, assinaturas.asaas_cliente),
            asaas_assinatura = NULL,
            pago_ate = GREATEST(assinaturas.pago_ate, EXCLUDED.pago_ate),
            acesso_ate = GREATEST(assinaturas.acesso_ate, EXCLUDED.acesso_ate),
            plano_no_proximo_ciclo = NULL,
            cancelada_em = NULL,
            -- Começo da assinatura NOVA: é por ele que um pagamento atrasado da
            -- antiga é reconhecido e não grava o id dela aqui.
            desde = now()
        """,
        registro["seller_id"],
        registro["plano"],
        registro["ciclo"],
        _id_de(checkout.get("customer")),
        pago_ate,
        acesso_ate,
    )
    return "plano-ativado"


async def _assinatura_criada(conn, assinatura: dict) -> str:
    """Liga o id da assinatura ao vendedor, pelo cliente do Asaas.

    É o que deixa cancelar durante o teste de 7 dias, antes de qualquer
    pagamento trazer o id. Se chegar antes do checkout pago (fila fora de
    ordem), não acha o cliente: o primeiro pagamento, ou a consulta ao Asaas
    na hora de cancelar, cobrem.
    """
    resultado = await conn.execute(
        """
        UPDATE assinaturas SET asaas_assinatura = $1
         WHERE asaas_cliente = $2 AND asaas_assinatura IS NULL AND cancelada_em IS NULL
        """,
        _id_de(assinatura),
        _id_de(assinatura.get("customer")),
    )
    return "assinatura-ligada" if resultado.endswith(" 1") else "assinatura-sem-dono"


async def _dono(conn, assinatura: str | None, cliente: str | None) -> asyncpg.Record | None:
    """A linha de `assinaturas` do pagamento: pela assinatura, ou pelo cliente."""
    if assinatura:
        linha = await conn.fetchrow(
            "SELECT * FROM assinaturas WHERE asaas_assinatura = $1 FOR UPDATE", assinatura
        )
        if linha is not None:
            return linha
    if cliente:
        return await conn.fetchrow(
            "SELECT * FROM assinaturas WHERE asaas_cliente = $1 FOR UPDATE", cliente
        )
    return None


async def _pagamento_confirmado(conn, pagamento: dict) -> str:
    linha = await _dono(
        conn, _id_de(pagamento.get("subscription")), _id_de(pagamento.get("customer"))
    )
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

    # O pagamento traz o id da assinatura que o checkout não trouxe: grava, se
    # ainda faltar e se não foi cancelada. E só se o pagamento é da assinatura
    # ATUAL: o `PAYMENT_RECEIVED` atrasado (até 32 dias, no cartão) de uma
    # assinatura antiga, de quem cancelou e recontratou, vence antes do começo
    # da nova, e gravaria o id antigo aqui — o cancelamento passaria a mirar
    # numa assinatura que já não existe, e a nova seguiria cobrando.
    await conn.execute(
        """
        UPDATE assinaturas SET asaas_assinatura = $2
         WHERE seller_id = $1 AND asaas_assinatura IS NULL AND cancelada_em IS NULL
           AND $2::text IS NOT NULL
           AND $3 >= (desde AT TIME ZONE 'America/Sao_Paulo')::date
        """,
        linha["seller_id"],
        _id_de(pagamento.get("subscription")),
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
        conn, _id_de(pagamento.get("subscription")), _id_de(pagamento.get("customer"))
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

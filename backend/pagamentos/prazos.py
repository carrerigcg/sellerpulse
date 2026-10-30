# backend/pagamentos/prazos.py
"""Até quando um pagamento dá acesso. Contas puras, sem banco.

O acesso tem prazo (`assinaturas.acesso_ate`) em vez de um estado que algum
agendador precisaria desligar: cada pagamento confirmado empurra o prazo, e
sem pagamento ele vence sozinho. Desenho em
docs/specs/2026-10-29-cobranca-asaas-design.md.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from dateutil.relativedelta import relativedelta

from backend.analytics._common import _TZ_VENDEDOR
from backend.planos import DIAS_DE_TOLERANCIA


def fim_do_periodo(inicio: date, ciclo: str) -> date:
    """Último dia coberto (exclusivo) por um pagamento que começa em `inicio`.

    `relativedelta` e não 30/365 dias: quem paga dia 31 de janeiro tem até o
    fim de fevereiro, não até 2 de março.
    """
    meses = 12 if ciclo == "anual" else 1
    return inicio + relativedelta(months=meses)


def hoje_do_vendedor() -> date:
    """O "hoje" no fuso do vendedor. O Render roda em UTC, e entre 21h e
    meia-noite de Brasília `date.today()` já seria amanhã."""
    return datetime.now(_TZ_VENDEDOR).date()


def meia_noite_do_vendedor(dia: date) -> datetime:
    """O começo do dia no fuso do vendedor: o dia é o dele, não o UTC."""
    return datetime.combine(dia, time.min, tzinfo=_TZ_VENDEDOR)


def prazos_de_um_pagamento(inicio: date, ciclo: str) -> tuple[datetime, datetime]:
    """`(pago_ate, acesso_ate)` de um pagamento do período que começa em `inicio`.

    `acesso_ate` leva os dias de tolerância: a cobrança seguinte que falha não
    corta o acesso no dia (decisão 4 da spec).
    """
    pago_ate = meia_noite_do_vendedor(fim_do_periodo(inicio, ciclo))
    return pago_ate, pago_ate + timedelta(days=DIAS_DE_TOLERANCIA)

# backend/pagamentos/asaas.py
"""Cliente mínimo da API do Asaas: só o que a cobrança usa.

Documentação: https://docs.asaas.com. A chave vai no header `access_token`
(não confundir com `asaas-access-token`, que é o token do WEBHOOK). Sandbox e
produção têm URL e chave diferentes, e uma chave do ambiente errado responde
401 `invalid_environment`.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import httpx

URL_PADRAO = "https://api-sandbox.asaas.com/v3"

# O Asaas exige User-Agent nas contas criadas depois de 13/06/2024.
_USER_AGENT = "SellerPulse/1.0"

_CICLO_DO_ASAAS = {"mensal": "MONTHLY", "anual": "YEARLY"}


class AsaasNaoConfigurado(RuntimeError):
    """Sem `ASAAS_API_KEY`: cobrar não é possível, e isso tem que ser dito."""


class AsaasErro(RuntimeError):
    def __init__(self, status: int, corpo: str) -> None:
        # O corpo de erro do Asaas descreve o campo inválido; nunca traz a
        # chave. Cortado para não encher o log.
        super().__init__(f"Asaas respondeu {status}: {corpo[:300]}")
        self.status = status


def configurado() -> bool:
    return bool(os.environ.get("ASAAS_API_KEY"))


def _cliente() -> httpx.AsyncClient:
    """Fábrica do cliente HTTP. Os testes trocam esta função por um transporte falso."""
    chave = os.environ.get("ASAAS_API_KEY")
    if not chave:
        raise AsaasNaoConfigurado("ASAAS_API_KEY não está configurada")
    return httpx.AsyncClient(
        base_url=os.environ.get("ASAAS_BASE_URL", URL_PADRAO).rstrip("/"),
        headers={"access_token": chave, "User-Agent": _USER_AGENT},
        timeout=20.0,
    )


async def _pede(metodo: str, caminho: str, corpo: dict | None = None) -> dict:
    async with _cliente() as cliente:
        resposta = await cliente.request(metodo, caminho, json=corpo)
    if resposta.status_code >= 400:
        raise AsaasErro(resposta.status_code, resposta.text)
    return resposta.json() if resposta.content else {}


def _reais(valor: Decimal) -> float:
    # O Asaas recebe número, em reais. Arredonda nos centavos ANTES de virar
    # float, para R$ 499,20 não sair 499.20000000000005.
    return float(valor.quantize(Decimal("0.01")))


async def criar_checkout(
    *,
    nome_do_item: str,
    valor: Decimal,
    ciclo: str,
    recorrente: bool,
    primeira_cobranca: date | None,
    cliente: dict,
    referencia: str,
    url_de_retorno: str,
) -> dict:
    """Cria o checkout hospedado e devolve `{id, link, ...}`.

    - Recorrente (mensal): `RECURRENT`, só cartão — é o que o checkout
      recorrente do Asaas aceita. `primeira_cobranca` adia a primeira
      cobrança (o teste de 7 dias).
    - Avulso (anual): `DETACHED`, Pix ou cartão.
    """
    corpo: dict = {
        "billingTypes": ["CREDIT_CARD"] if recorrente else ["CREDIT_CARD", "PIX"],
        "chargeTypes": ["RECURRENT"] if recorrente else ["DETACHED"],
        "minutesToExpire": 60,
        "externalReference": referencia,
        "callback": {
            "successUrl": f"{url_de_retorno}?checkout=ok",
            "cancelUrl": f"{url_de_retorno}?checkout=cancelado",
            "expiredUrl": f"{url_de_retorno}?checkout=expirado",
        },
        "items": [{"name": nome_do_item[:30], "quantity": 1, "value": _reais(valor)}],
        "customerData": cliente,
    }
    if recorrente:
        corpo["subscription"] = {
            "cycle": _CICLO_DO_ASAAS[ciclo],
            "nextDueDate": (primeira_cobranca or date.today()).isoformat(),
        }
    return await _pede("POST", "/checkouts", corpo)


async def mudar_valor_da_assinatura(assinatura: str, valor: Decimal) -> dict:
    """Valor novo a partir da PRÓXIMA cobrança (sem `updatePendingPayments`).

    A cobrança já gerada fica como está: é a decisão 6 da spec (a diferença do
    mês corrente fica por nossa conta).
    """
    return await _pede("PUT", f"/subscriptions/{assinatura}", {"value": _reais(valor)})


async def remover_assinatura(assinatura: str) -> dict:
    """Encerra a recorrência. O Asaas remove as cobranças pendentes dela."""
    return await _pede("DELETE", f"/subscriptions/{assinatura}")

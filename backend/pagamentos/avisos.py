# backend/pagamentos/avisos.py
"""Os avisos por e-mail que o Asaas manda a quem paga: recibo, vencimento, atraso.

O cliente que o checkout do Asaas cria na hora do pagamento nasce com todos os
avisos sem e-mail e sem SMS, e a conta não tem configuração geral: é por
cliente (suporte do Asaas, 2026-11-04). Criar o cliente antes exigiria telefone
e endereço, que o SellerPulse não coleta. Então liga depois, assim que o
cliente aparece. O SMS fica como está.

O recibo do PRIMEIRO pagamento sai antes de dar tempo de ligar: ele fica na
tela "Minha assinatura" (`GET /conta/pagamentos`).

Desenho em docs/specs/2026-11-04-avisos-e-comprovantes-design.md.
"""

from __future__ import annotations

import json
import logging

from backend.pagamentos import asaas

_log = logging.getLogger(__name__)


async def garante(pool, cliente: str | None) -> None:
    """Liga os avisos por e-mail de um cliente nosso, uma vez só.

    Roda depois da resposta (webhook e tela), então falha não derruba nada:
    vira aviso no log, e a próxima chance tenta de novo.
    """
    if not cliente:
        return
    async with pool.acquire() as conn:
        # Só cliente de um checkout nosso: a conta do Asaas pode ter outros.
        # A marca mora no log de eventos, como a da desistência.
        pendente = await conn.fetchval(
            """
            SELECT (EXISTS (SELECT 1 FROM checkouts WHERE asaas_cliente = $1)
                    OR EXISTS (SELECT 1 FROM assinaturas WHERE asaas_cliente = $1))
               AND NOT EXISTS (SELECT 1 FROM eventos_do_gateway WHERE id = $2)
            """,
            cliente,
            f"avisos:{cliente}",
        )
    if not pendente:
        return
    try:
        ligados = await asaas.ligar_avisos_por_email(cliente)
    except (asaas.AsaasErro, asaas.AsaasNaoConfigurado) as erro:
        _log.warning("[asaas] avisos do cliente %s ficaram desligados: %s", cliente, erro)
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO eventos_do_gateway (id, tipo, payload) VALUES ($1, $2, $3::jsonb) "
            "ON CONFLICT (id) DO NOTHING",
            f"avisos:{cliente}",
            "AVISOS_LIGADOS",
            json.dumps({"customer": cliente, "ligados": ligados}),
        )

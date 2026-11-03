# backend/retencao.py
"""Os prazos de guarda que a Política promete (seção 7), aplicados uma vez por dia.

- A credencial do Mercado Livre sai 30 dias depois do fim do plano.
- Os dados da loja saem depois de 12 meses sem plano. A conta fica: quem voltar
  reconecta e a ingestão traz o histórico de novo.
- O registro de acesso sai aos 6 meses, mesmo de quem não voltou a entrar.
- A prova do aceite e os checkouts de conta excluída saem aos 5 anos.
- Os eventos do Asaas saem aos 5 anos do recebimento.

"Fim do plano" é `assinaturas.acesso_ate`. Plano dado à mão (`acesso_ate` nulo) e a
conta de demonstração nunca vencem. Desenho em
docs/specs/2026-11-03-retencao-automatica-design.md.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os

import asyncpg

_log = logging.getLogger(__name__)

# O que é "dado da loja" e sai aos 12 meses. `order_items` antes de `orders` só por
# clareza: o cascade cuidaria disso.
DADOS_DA_LOJA = (
    "order_items",
    "orders",
    "items_cache",
    "categories_cache",
    "claims",
    "sync_jobs",
    "product_costs",
    "item_visits",
    "shipment_costs",
    "oauth_tokens",
)
# O que fica: a conta, o plano e o que a lei manda guardar. Tabela nova com
# `seller_id` precisa entrar numa das duas listas, ou o teste de cobertura cai.
FICAM = ("sellers", "assinaturas", "aceites_de_termos", "checkouts", "contas_excluidas")

UM_DIA = 24 * 60 * 60

# FOR UPDATE: o pagamento de uma recontratação que chegue no meio da limpeza
# espera ela terminar e, depois, encontra o prazo já renovado na própria linha.
_VENCIDOS = """
    SELECT a.seller_id FROM assinaturas a JOIN sellers s ON s.id = a.seller_id
     WHERE NOT s.is_demo AND a.acesso_ate < now() - $1::text::interval
       FOR UPDATE OF a
"""


async def aplica_retencao(pool: asyncpg.Pool) -> dict[str, int]:
    """Apaga o que passou do prazo e devolve quantas linhas saíram de cada lugar.

    Uma transação por etapa: um vendedor grande que estoure o tempo não pode
    desfazer também a limpeza do registro de acesso, que é obrigação legal.
    """
    saiu: dict[str, int] = {}
    async with pool.acquire() as conn:
        # Primeiro, e fora das outras: é a obrigação legal, e uma falha mais adiante
        # não pode adiá-la. A folga de 1 hora é a do endpoint: `hora` guarda o começo
        # do período.
        saiu["registros_de_acesso"] = _total(
            await conn.execute(
                "DELETE FROM registros_de_acesso WHERE hora < now() - interval '6 months 1 hour'"
            )
        )

        async with conn.transaction():
            sem_token = [r["seller_id"] for r in await conn.fetch(_VENCIDOS, "30 days")]
            saiu["credenciais"] = _total(
                await conn.execute(
                    "DELETE FROM oauth_tokens WHERE seller_id = ANY($1::uuid[])", sem_token
                )
            )
            # A tela diz "conectado" pelo `ml_seller_id`. Sem zerar, quem voltasse a
            # pagar veria "Conectado como X", sem o botão de conectar, e o worker
            # falharia sem credencial. O callback grava de novo e pede a ingestão.
            await conn.execute(
                "UPDATE sellers SET ml_seller_id = NULL WHERE id = ANY($1::uuid[])", sem_token
            )

        async with conn.transaction():
            sem_dados = [r["seller_id"] for r in await conn.fetch(_VENCIDOS, "12 months")]
            for tabela in DADOS_DA_LOJA:
                total = _total(
                    await conn.execute(
                        f"DELETE FROM {tabela} WHERE seller_id = ANY($1::uuid[])",  # noqa: S608
                        sem_dados,
                    )
                )
                if total:
                    saiu[tabela] = total
            # Sem a marca d'água, quem voltar e reconectar recebe a ingestão inicial,
            # e não um delta sobre um histórico que já não existe.
            await conn.execute(
                "UPDATE sellers SET last_synced_at = NULL WHERE id = ANY($1::uuid[])", sem_dados
            )

        async with conn.transaction():
            prescritas = [
                r["seller_id"]
                for r in await conn.fetch(
                    "DELETE FROM contas_excluidas WHERE excluida_em < now() - interval '5 years' "
                    "RETURNING seller_id"
                )
            ]
            for tabela in ("aceites_de_termos", "checkouts"):
                saiu[tabela] = _total(
                    await conn.execute(
                        f"DELETE FROM {tabela} WHERE seller_id = ANY($1::uuid[])",  # noqa: S608
                        prescritas,
                    )
                )
            saiu["contas_excluidas"] = len(prescritas)

        # Os "registros da cobrança" que a Política guarda por 5 anos. O evento
        # não tem vendedor: o prazo conta do recebimento, para todos.
        saiu["eventos_do_gateway"] = _total(
            await conn.execute(
                "DELETE FROM eventos_do_gateway WHERE recebido_em < now() - interval '5 years'"
            )
        )
    return {chave: total for chave, total in saiu.items() if total}


def _total(status: str) -> int:
    return int(status.rsplit(" ", 1)[-1])


def retencao_habilitada() -> bool:
    """Opt-in, como o refresh da demo: esta rotina APAGA. Esquecer a variável deixa
    dado vencido por mais tempo (ruim), e um default ligado apagaria dado em todo
    clone ou runner de CI que importasse `backend.main` (pior)."""
    return os.environ.get("RETENCAO_IN_PROCESS") == "1"


async def loop_diario(pool: asyncpg.Pool, *, parar: asyncio.Event) -> None:
    """Roda no boot e depois a cada 24 horas, até `parar`. Falha vira log, nunca
    derruba a API."""
    while not parar.is_set():
        try:
            _log.info("[retencao] %s", await aplica_retencao(pool) or "nada vencido")
        except Exception:  # noqa: BLE001 — boundary da task de fundo
            _log.exception("[retencao] falhou")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(parar.wait(), timeout=UM_DIA)

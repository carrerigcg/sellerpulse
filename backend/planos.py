# backend/planos.py
"""O que cada plano libera. É o ÚNICO lugar que sabe disso.

Os routers perguntam a este módulo (`libera`, `dias_de_historico`, ...) e não
têm `if plano == "essencial"` próprio: uma regra de plano espalhada por cinco
routers é uma regra que alguém esquece de mudar em um deles.

Desenho e decisões em docs/specs/2026-10-28-planos-e-acesso-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

# Versão dos Termos de Uso que o vendedor precisa ter aceitado. Mudar este
# valor obriga todo mundo a aceitar de novo: é o que se quer quando o texto
# muda. A mesma versão está escrita nos textos de `frontend/content/legal/`, e
# um teste falha se divergirem.
VERSAO_DOS_TERMOS = "2026-11-v1"

# Decisões da spec de cobrança (docs/specs/2026-10-29-cobranca-asaas-design.md).
MESES_PAGOS_NO_ANUAL = 10
DIAS_DE_TOLERANCIA = 7
DIAS_DE_TESTE = 7
# Só o Exclusive mensal tem teste (decisão 7): é o plano que se quer vender.
PLANOS_COM_TESTE = frozenset({"exclusive"})


class Recurso(StrEnum):
    # Mais de 10 produtos na curva ABC.
    ABC_COMPLETA = "abc-completa"
    # Visitas e conversão por anúncio (vêm junto com a ABC).
    DESEMPENHO_ANUNCIOS = "desempenho-anuncios"
    CLIENTES = "clientes"
    COHORT = "cohort"
    # Exportar gera o CSV no navegador, a partir do que as outras telas já
    # carregaram; a trava dele é de tela. Está aqui para o front saber, pela
    # mesma lista, o que mostrar com cadeado.
    EXPORTAR = "exportar"
    # Sincronizar fora da diária agendada: no login e pelo botão.
    SYNC_SOB_DEMANDA = "sync-sob-demanda"
    # Margem negativa e anúncio parado, no Resumo. Só o Premium.
    ALERTAS = "alertas"


@dataclass(frozen=True)
class Plano:
    nome: str
    # Por mês, em reais. É o valor que vai para o checkout: o navegador nunca
    # diz quanto cobrar. A vitrine mostra o mesmo número
    # (`frontend/components/planos/cartoes-de-planos.tsx`), e um teste confere
    # que os dois batem.
    preco_mensal: Decimal
    recursos: frozenset[Recurso]
    # None = sem limite além do que a ingestão trouxe.
    dias_de_historico: int | None
    # None = a curva inteira.
    produtos_na_abc: int | None
    # Fora de venda: não entra em checkout nem em troca, mas quem já tem continua.
    a_venda: bool = True
    # De quanto em quanto tempo a sincronização agendada traz o dado novo.
    horas_entre_syncs: int = 24

    def libera(self, recurso: Recurso) -> bool:
        return recurso in self.recursos

    def preco(self, ciclo: str) -> Decimal:
        """Valor cobrado no ciclo. O anual é 10 mensais: paga 10, leva 12."""
        return self.preco_mensal * MESES_PAGOS_NO_ANUAL if ciclo == "anual" else self.preco_mensal


_TUDO = frozenset(Recurso)

PLANOS: dict[str, Plano] = {
    "essencial": Plano(
        nome="essencial",
        preco_mensal=Decimal("49.90"),
        recursos=frozenset(),
        dias_de_historico=90,
        produtos_na_abc=10,
    ),
    # O Exclusive libera tudo, menos o que é só do Premium (os alertas). O que
    # mais vai diferenciá-los (MCP com a conta real, várias contas) entra com
    # cada feature (decisão 8 da spec). Sem corte no Exclusive, ele entregaria
    # com o tempo o histórico longo que o Premium vai vender.
    "exclusive": Plano(
        nome="exclusive",
        preco_mensal=Decimal("79.90"),
        recursos=_TUDO - {Recurso.ALERTAS},
        dias_de_historico=180,
        produtos_na_abc=None,
    ),
    "premium": Plano(
        nome="premium",
        preco_mensal=Decimal("139.90"),
        recursos=_TUDO,
        # 12 meses é o que o ML devolve no `/orders/search` (medido em
        # 2026-11-06) e o que a vitrine promete. Sem corte, o histórico
        # cresceria além do que se vende.
        dias_de_historico=365,
        produtos_na_abc=None,
        # Volta à venda quando as funções que o diferenciam existirem.
        a_venda=False,
        horas_entre_syncs=6,
    ),
}

# Assinatura que ainda dá acesso, sobre `assinaturas` com o apelido `a`. Prazo
# vencido conta como sem plano: é assim que a inadimplência e o cancelamento
# desligam o acesso, sem agendador. Uma condição só, para o painel e o worker
# não discordarem sobre quem tem plano.
ASSINATURA_VIGENTE = "(a.acesso_ate IS NULL OR a.acesso_ate > now())"

# O que o backfill sempre busca, qualquer que seja o plano: quem sobe do
# Essencial para o Exclusive já tem os 6 meses, sem esperar outra busca.
DIAS_DE_INGESTAO_MINIMO = 180


def dias_de_ingestao(plano: Plano | None) -> int:
    """Quantos dias o backfill busca no ML para este plano.

    O que o plano mostra, com piso de 180. Spec
    docs/specs/2026-11-06-premium-historico-de-12-meses-design.md, decisão 2.
    """
    dias = plano.dias_de_historico if plano is not None else None
    return max(DIAS_DE_INGESTAO_MINIMO, dias or DIAS_DE_INGESTAO_MINIMO)


async def plano_vigente(pool, seller_id) -> Plano | None:
    """O plano do vendedor, para quem não passa pelo FastAPI (o worker)."""
    async with pool.acquire() as conn:
        nome = await conn.fetchval(
            f"SELECT a.plano FROM assinaturas a WHERE a.seller_id = $1 AND {ASSINATURA_VIGENTE}",
            seller_id,
        )
    return PLANOS[nome] if nome is not None else None

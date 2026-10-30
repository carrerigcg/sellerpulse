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
# muda. Hoje os termos são rascunho; a versão revisada pelo advogado entra com
# outro nome e pede aceite novo.
VERSAO_DOS_TERMOS = "2026-10-28-rascunho"

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
    # Exclusive e Premium liberam tudo o que existe hoje. O que vai
    # diferenciá-los (MCP com a conta real, alertas, várias contas) entra com
    # cada feature (decisão 8 da spec).
    "exclusive": Plano(
        nome="exclusive",
        preco_mensal=Decimal("79.90"),
        recursos=_TUDO,
        dias_de_historico=None,
        produtos_na_abc=None,
    ),
    "premium": Plano(
        nome="premium",
        preco_mensal=Decimal("139.90"),
        recursos=_TUDO,
        dias_de_historico=None,
        produtos_na_abc=None,
    ),
}

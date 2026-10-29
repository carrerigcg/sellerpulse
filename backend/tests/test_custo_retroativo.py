"""Custo retroativo: a opção "aplicar também às vendas anteriores sem custo".

O que estes testes protegem são as duas metades da decisão de 2026-10-28
(docs/specs/2026-10-28-custo-retroativo-design.md):

- o retroativo PREENCHE o histórico que está sem custo, que é o motivo da
  feature;
- e NUNCA reescreve um período que já tinha custo, que é a decisão 4 da spec
  de 2026-10-13. Um custo corrigido hoje não pode mudar em silêncio a margem
  de um mês fechado.

As datas são relativas a hoje porque a exceção do "mesmo dia" depende de
`criado_em`, que o banco grava com `now()`.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from backend.analytics.custos_pg import (
    VIGENCIA_DO_HISTORICO,
    gravar_custo,
    hoje_do_vendedor,
    remover_custo,
)
from backend.analytics.metrics_pg import fluxo_financeiro

from .test_custo_de_produto import _custo, _pedido

HOJE = hoje_do_vendedor()


def _as_13h(dia) -> str:
    """13:00 UTC = 10:00 em Brasília: longe da meia-noite nos dois fusos."""
    return datetime.combine(dia, time(13, 0), tzinfo=UTC).isoformat()


async def _custo_do_dia(pool, sid, dia) -> float:
    janela = (dia.isoformat(), (dia + timedelta(days=1)).isoformat())
    linha = (await fluxo_financeiro(pool, sid, *janela)).iloc[0]
    return float(linha["custo_produtos"])


async def _vigencias(pool, sid, item="MLB1") -> dict:
    async with pool.acquire() as conn:
        linhas = await conn.fetch(
            "SELECT vigente_desde, custo_unitario FROM product_costs"
            " WHERE seller_id=$1 AND item_id=$2",
            sid,
            item,
        )
    return {linha["vigente_desde"]: float(linha["custo_unitario"]) for linha in linhas}


async def _envelhece(pool, sid, vigencia, item="MLB1"):
    """Faz a linha parecer gravada num dia anterior (criado_em antigo)."""
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE product_costs SET criado_em = now() - interval '3 days'"
            " WHERE seller_id=$1 AND item_id=$2 AND vigente_desde=$3",
            sid,
            item,
            vigencia,
        )


async def test_retroativo_preenche_o_historico_sem_custo(pg_pool, test_seller):
    """O motivo da feature: quem informa o custo hoje vê o passado com custo."""
    _, sid = test_seller
    passado = HOJE - timedelta(days=60)
    await _pedido(pg_pool, sid, 1, _as_13h(passado), [("MLB1", 2, 50.0)])

    await gravar_custo(pg_pool, sid, "MLB1", 10.0, retroativo=True)

    assert await _custo_do_dia(pg_pool, sid, passado) == 20.0, "2 unidades a 10,00"


async def test_sem_a_opcao_continua_valendo_so_de_hoje_em_diante(pg_pool, test_seller):
    _, sid = test_seller
    passado = HOJE - timedelta(days=60)
    await _pedido(pg_pool, sid, 1, _as_13h(passado), [("MLB1", 2, 50.0)])

    await gravar_custo(pg_pool, sid, "MLB1", 10.0)

    assert await _custo_do_dia(pg_pool, sid, passado) == 0.0


async def test_retroativo_nunca_reescreve_periodo_que_ja_tinha_custo(pg_pool, test_seller):
    """A decisão 2: só preenche o que está sem custo.

    Custo de 30 informado há 30 dias. Hoje o vendedor salva 35 com a opção
    ligada: a venda de 15 dias atrás continua com 30, e só a de 60 dias atrás,
    que estava sem custo, ganha 35.
    """
    _, sid = test_seller
    antiga, recente = HOJE - timedelta(days=60), HOJE - timedelta(days=15)
    await _pedido(pg_pool, sid, 1, _as_13h(antiga), [("MLB1", 1, 100.0)])
    await _pedido(pg_pool, sid, 2, _as_13h(recente), [("MLB1", 1, 100.0)])
    await _custo(pg_pool, sid, "MLB1", (HOJE - timedelta(days=30)).isoformat(), 30.0)

    await gravar_custo(pg_pool, sid, "MLB1", 35.0, retroativo=True)

    assert await _custo_do_dia(pg_pool, sid, recente) == 30.0, "período informado ficou intacto"
    assert await _custo_do_dia(pg_pool, sid, antiga) == 35.0, "só o que estava sem custo ganhou"


async def test_inicio_do_historico_preenchido_em_outro_dia_nao_muda(pg_pool, test_seller):
    """A decisão 4: com a opção sempre ligada, subir o preço não mexe no passado."""
    _, sid = test_seller
    antiga = HOJE - timedelta(days=60)
    await _pedido(pg_pool, sid, 1, _as_13h(antiga), [("MLB1", 1, 100.0)])
    await gravar_custo(pg_pool, sid, "MLB1", 30.0, retroativo=True)
    await _envelhece(pg_pool, sid, VIGENCIA_DO_HISTORICO)

    await gravar_custo(pg_pool, sid, "MLB1", 45.0, retroativo=True)

    assert await _custo_do_dia(pg_pool, sid, antiga) == 30.0


async def test_no_mesmo_dia_salvar_de_novo_corrige_o_retroativo(pg_pool, test_seller):
    """A exceção do mesmo dia: o erro de digitação não fica preso no histórico."""
    _, sid = test_seller
    antiga = HOJE - timedelta(days=60)
    await _pedido(pg_pool, sid, 1, _as_13h(antiga), [("MLB1", 1, 100.0)])

    await gravar_custo(pg_pool, sid, "MLB1", 300.0, retroativo=True)  # digitou um zero a mais
    await gravar_custo(pg_pool, sid, "MLB1", 30.0, retroativo=True)

    assert await _custo_do_dia(pg_pool, sid, antiga) == 30.0


async def test_esvaziar_o_campo_desfaz_tambem_o_retroativo_de_hoje(pg_pool, test_seller):
    _, sid = test_seller
    antiga = HOJE - timedelta(days=60)
    await _pedido(pg_pool, sid, 1, _as_13h(antiga), [("MLB1", 1, 100.0)])
    await gravar_custo(pg_pool, sid, "MLB1", 30.0, retroativo=True)

    assert await remover_custo(pg_pool, sid, "MLB1") is True

    assert await _vigencias(pg_pool, sid) == {}
    assert await _custo_do_dia(pg_pool, sid, antiga) == 0.0


async def test_esvaziar_nao_apaga_o_retroativo_de_outro_dia(pg_pool, test_seller):
    """Desfazer é do dia. O histórico preenchido antes continua."""
    _, sid = test_seller
    await gravar_custo(pg_pool, sid, "MLB1", 30.0, retroativo=True)
    await _envelhece(pg_pool, sid, VIGENCIA_DO_HISTORICO)

    await remover_custo(pg_pool, sid, "MLB1")

    assert await _vigencias(pg_pool, sid) == {VIGENCIA_DO_HISTORICO: 30.0}


async def test_retroativo_isola_por_seller(pg_pool, test_seller, outro_seller):
    _, sid = test_seller
    _, outro = outro_seller
    await gravar_custo(pg_pool, outro, "MLB1", 999.0, retroativo=True)

    await gravar_custo(pg_pool, sid, "MLB1", 30.0, retroativo=True)

    assert await _vigencias(pg_pool, sid) == {VIGENCIA_DO_HISTORICO: 30.0, HOJE: 30.0}

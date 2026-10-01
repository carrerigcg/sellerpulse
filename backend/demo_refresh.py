# backend/demo_refresh.py
"""Mantem o seller de demonstracao com dado que termina HOJE.

O gerador (`src/demo_data.py`) nasceu com uma ancora FIXA porque `data/demo.db`
e versionado e o golden do PDF depende dos numeros exatos. O efeito colateral
foi que a demo publica em `/demo` congelou: a ultima venda ficou em
2026-07-31 e, a cada dia que passa, a janela com dado se afasta mais do "hoje"
que o visitante ve no date picker. Numa pagina cuja unica funcao e atrair
quem ainda nao tem conta, arrastar a data pra fora de uma janela de tres meses
mostrava tela vazia.

Este modulo e separado do `backend/seed.py` de proposito. O `seed.py` se
apresenta (e se comporta) como "seguro de rodar de novo": todo INSERT dele tem
`ON CONFLICT DO NOTHING`. O que esta aqui e o oposto -- `DELETE` seguido de
`INSERT` -- e nao da pra descrever as duas politicas no mesmo docstring sem
que uma minta sobre a outra. Um DELETE morando num modulo que todo mundo le
como idempotente e exatamente a forma de alguem chamar a funcao errada.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta

from backend.seed import seed_na_conexao

_log = logging.getLogger(__name__)

# 26 semanas = 182 dias, o mais proximo em semanas inteiras dos 180 dias que um
# seller real recebe no backfill (`JANELAS_BACKFILL * DIAS_POR_JANELA` em
# `backend/worker/runner.py`). A demo tem que mostrar a MESMA profundidade de
# historico que o produto entrega de verdade: com as 12 semanas do default do
# `seed_postgres` (~3 meses), o visitante avalia metade do que receberia ao
# conectar a conta dele -- e as analises que dependem de historico longo
# (cohort, RFM) ficam mais pobres na vitrine do que no produto.
SEMANAS_DEMO = 26

# A partir de quantos dias sem venda nova a demo e considerada vencida.
#
# 7 dias nao e um numero escolhido por gosto: e o menor valor que NAO pode
# entrar em loop. `generate_orders` espalha os pedidos da ultima semana em
# `week_start + 0..6 dias`, com `week_start = anchor - 7 dias`. O pedido mais
# novo cai tipicamente ~1 dia antes da ancora, mas no pior caso do RNG (nenhum
# pedido com `day_offset = 6` na ultima semana) pode cair ate ~7 dias antes.
# Com um limite menor que isso, uma regeneracao poderia terminar ja produzindo
# dado "vencido" -- e como o gatilho roda em todo cold start, o Render (que
# hiberna o tempo todo) regeraria a base a cada visita, pra sempre.
#
# O custo do outro lado e pequeno: no pior caso a demo fica ~8 dias atras de
# hoje, o que continua dentro de qualquer janela de "ultimos 30 dias".
DIAS_PARA_VENCER = 7


async def regenera_demo(
    pool,
    seller_id,
    *,
    anchor: datetime,
    seed: int | None = None,
    n_categories: int = 10,
    n_products: int = 50,
    weeks_back: int = SEMANAS_DEMO,
    claim_rate: float = 0.04,
) -> dict[str, int]:
    """Apaga os dados sinteticos de `seller_id` e re-semeia com `anchor`.

    Por que apagar em vez de re-semear por cima: `seed_postgres` e idempotente
    via `ON CONFLICT DO NOTHING`, e `order_id` vem de `order_id_counter`
    (comeca em 1_000_000 e incrementa) -- derivado da sequencia do RNG, NAO
    das datas. Re-semear com a mesma seed e outra ancora produz exatamente os
    mesmos `order_id`, todo INSERT colide, e o refresh reporta sucesso sem ter
    mudado uma linha. As datas velhas ficariam lá pra sempre, em silencio.

    Levanta se o seller nao estiver marcado `is_demo` -- ver `_exige_demo`.

    Returns:
        as contagens de linhas inseridas, como `seed_postgres`.
    """
    # DELETE e INSERT na MESMA transacao. Separados, uma falha no meio (o free
    # tier do Render hiberna, o Supabase derruba conexao) deixaria a demo
    # publica vazia ate o proximo cold start -- estado pior que o dado velho
    # que estamos consertando.
    async with pool.acquire() as conn, conn.transaction():
        await _exige_demo(conn, seller_id)

        # `order_items` NAO aparece aqui de proposito: a FK dela e
        # `(seller_id, order_id) references orders on delete cascade`
        # (0001_init.sql), entao o DELETE de `orders` ja leva os itens. As
        # outras tres referenciam `sellers(id)`, nao `orders` -- o cascade
        # delas so dispara se o SELLER for apagado, que e justamente o que
        # este refresh nao faz. Precisam de DELETE explicito.
        #
        # `sellers`, `oauth_tokens` e `sync_jobs` ficam intactos: a linha do
        # seller, o vinculo OAuth e o historico da fila nao sao dado
        # sintetico, e apagar `sellers` cascatearia pra tudo.
        await conn.execute("DELETE FROM claims WHERE seller_id = $1", seller_id)
        await conn.execute("DELETE FROM orders WHERE seller_id = $1", seller_id)
        await conn.execute("DELETE FROM items_cache WHERE seller_id = $1", seller_id)
        await conn.execute("DELETE FROM categories_cache WHERE seller_id = $1", seller_id)

        # `seed_na_conexao` e nao `seed_postgres`: o segundo pegaria uma conexao
        # NOVA do pool e abriria transacao propria, fora desta -- os DELETEs
        # acima commitariam (ou nao) independentemente do seed, que e
        # exatamente a janela de "demo vazia" que esta transacao existe pra
        # fechar.
        extras = {} if seed is None else {"seed": seed}
        contagens = await seed_na_conexao(
            conn,
            seller_id,
            anchor=anchor,
            n_categories=n_categories,
            n_products=n_products,
            weeks_back=weeks_back,
            claim_rate=claim_rate,
            **extras,
        )

    _log.info(
        "[demo] seller %s regenerado com ancora %s: %s pedidos",
        seller_id,
        anchor.isoformat(),
        contagens["orders"],
    )
    return contagens


async def _exige_demo(conn, seller_id) -> None:
    """Aborta se `seller_id` nao estiver marcado `is_demo = true`.

    A linha mais importante deste modulo. O que vem depois dela e
    `DELETE FROM orders WHERE seller_id = $1` -- com o id errado (typo numa env
    var de deploy, bug num chamador futuro) isso apaga o faturamento inteiro de
    um cliente real. `is_demo` e a mesma marca que `routers/demo.py` exige pra
    SERVIR o seller sem autenticacao (migration 0007), entao os dois lados da
    demo concordam sobre quem ela e.

    Levanta em vez de voltar quieto: um refresh que descobre que o alvo nao e
    uma demo nao esta num caso de borda esperado, esta apontado pro seller
    errado. Retornar `None` aqui deixaria quem chama achando que regenerou.
    """
    marcado = await conn.fetchval("SELECT is_demo FROM sellers WHERE id = $1", seller_id)
    if marcado is None:
        raise ValueError(f"seller {seller_id} nao existe -- refresh de demo abortado")
    if not marcado:
        raise ValueError(
            f"seller {seller_id} nao esta marcado is_demo -- refresh de demo abortado "
            "(esta funcao APAGA os pedidos do seller antes de re-semear)"
        )


async def regenera_demo_se_vencida(pool) -> str:
    """Regenera a demo se a venda mais recente dela estiver velha.

    Chamada no `lifespan` da API (`backend/main.py`), em task de fundo. NUNCA
    levanta por ambiente nao configurado: API sem demo e o caso normal em
    desenvolvimento e na CI, e derrubar o boot por isso trocaria um problema
    cosmetico por indisponibilidade.

    Returns:
        string curta de status pra quem chama logar. Valores:
        `sem-env`, `env-invalida`, `seller-ausente`, `nao-e-demo`,
        `atual`, `regenerada`.
    """
    valor = os.environ.get("DEMO_SELLER_ID")
    if not valor:
        _log.info("[demo] DEMO_SELLER_ID ausente -- refresh da demo nao se aplica")
        return "sem-env"
    try:
        seller_id = uuid.UUID(valor)
    except ValueError:
        # Sem o valor no log: ele vem do ambiente de producao.
        _log.warning("[demo] DEMO_SELLER_ID nao e um UUID -- refresh da demo ignorado")
        return "env-invalida"

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT s.is_demo,
                   (SELECT max(o.date_closed) FROM orders o WHERE o.seller_id = s.id) AS mais_nova
            FROM sellers s
            WHERE s.id = $1
            """,
            seller_id,
        )

    # Os dois casos abaixo sao exatamente os que `regenera_demo` trata como
    # erro. Aqui eles sao esperados (banco de teste, ambiente novo, deploy sem
    # demo semeada), entao viram no-op com log em vez de excecao -- e por isso
    # este gatilho NAO chama `regenera_demo` antes de checar.
    if row is None:
        _log.warning("[demo] DEMO_SELLER_ID aponta pra seller inexistente -- refresh ignorado")
        return "seller-ausente"
    if not row["is_demo"]:
        _log.warning("[demo] seller da demo nao esta marcado is_demo -- refresh ignorado")
        return "nao-e-demo"

    agora = datetime.now(UTC)
    mais_nova = row["mais_nova"]
    if mais_nova is not None and (agora - mais_nova) < timedelta(days=DIAS_PARA_VENCER):
        _log.info("[demo] venda mais recente em %s -- demo atual, nada a fazer", mais_nova.date())
        return "atual"

    _log.info(
        "[demo] venda mais recente %s -- regenerando %s semanas ate %s",
        "inexistente" if mais_nova is None else mais_nova.date(),
        SEMANAS_DEMO,
        agora.date(),
    )
    await regenera_demo(pool, seller_id, anchor=agora)
    return "regenerada"

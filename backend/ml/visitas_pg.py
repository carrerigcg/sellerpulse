"""Colheita de visitas por anuncio.

Modulo separado de `ingest_pg.py` porque o dado e de outra natureza. Pedido o
Mercado Livre guarda para sempre; visita nao:

    janela consultavel    150 dias
    atraso                ~48h
    granularidade         um numero por item, por dia

Dai as tres regras que governam este arquivo:

1. **Se nao colher, perde.** Nenhuma chamada futura traz de volta o que saiu
   da janela de 150 dias. O primeiro sync de um seller colhe o maximo
   disponivel justamente por isso.
2. **A borda de 48h e sempre recolhida.** Os dois ultimos dias costumam vir
   subcontados, e sao reconsultados a cada sincronizacao.
3. **Recolher substitui, nunca soma.** Visita e contagem fechada do dia. O
   upsert bate na chave (seller_id, item_id, dia).
"""

from __future__ import annotations

import contextlib
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta

from src.ml_client import MLAPIError, MLClient

# Quantos dias da borda recente sao reconsultados a cada colheita.
#
# Dois, porque o ML leva ~48h pra consolidar. Reconsultar e barato (entra na
# mesma chamada que ja seria feita) e e o unico jeito de corrigir a
# subcontagem -- o valor de ontem colhido ontem esta errado por construcao.
DIAS_DE_BORDA = 2

_ITENS_VENDIDOS = """
    SELECT DISTINCT item_id
      FROM order_items
     WHERE seller_id = $1
     ORDER BY item_id
"""

# A lista de itens vem de `order_items`, nao do catalogo do ML.
#
# Produto que nunca vendeu nao tem conversao pra calcular, e buscar o catalogo
# inteiro multiplicaria as chamadas sem responder nenhuma pergunta da tela.
#
# CONSEQUENCIA ACEITA E REGISTRADA: produto com muitas visitas e ZERO vendas
# nao aparece -- e esse e justamente um caso interessante ("e visto e ninguem
# compra"). Fica pra versao que cruzar com o catalogo.

_ULTIMO_DIA_COLHIDO = """
    SELECT max(dia) FROM item_visits WHERE seller_id = $1
"""

_UPSERT_VISITAS = """
    INSERT INTO item_visits (seller_id, item_id, dia, visitas, colhido_em)
    VALUES ($1, $2, $3, $4, now())
    ON CONFLICT (seller_id, item_id, dia)
    DO UPDATE SET visitas = excluded.visitas, colhido_em = excluded.colhido_em
"""


@dataclass
class ResultadoVisitas:
    itens_processados: int = 0
    dias_gravados: int = 0
    warnings: list[str] = field(default_factory=list)


async def itens_a_colher(pool, seller_id: uuid.UUID) -> list[str]:
    """Itens que este vendedor ja vendeu, em ordem estavel.

    A ordem importa: o cursor do job guarda o ultimo item concluido, e uma
    ordem instavel faria a retomada pular ou repetir itens.
    """
    async with pool.acquire() as conn:
        linhas = await conn.fetch(_ITENS_VENDIDOS, seller_id)
    return [linha["item_id"] for linha in linhas]


async def janela_a_pedir(pool, seller_id: uuid.UUID, *, hoje: date | None = None) -> int:
    """Quantos dias pedir ao ML nesta colheita.

    Primeiro sync (nenhuma visita colhida ainda): o maximo que a API permite,
    porque o que nao for colhido agora sai da janela e some para sempre.

    Sync seguinte: do ultimo dia colhido menos `DIAS_DE_BORDA` ate hoje. Isso
    e o que corrige a subcontagem da janela de 48h, e e seguro porque o upsert
    substitui em vez de somar.

    Nunca excede `MLClient.MAX_DIAS_DE_VISITAS`: uma conta com um ano de
    pedidos pediria 365 dias e a chamada falharia inteira, perdendo tambem os
    150 dias validos que existiam.
    """
    hoje = hoje or date.today()
    async with pool.acquire() as conn:
        ultimo = await conn.fetchval(_ULTIMO_DIA_COLHIDO, seller_id)

    if ultimo is None:
        return MLClient.MAX_DIAS_DE_VISITAS

    desde = ultimo - timedelta(days=DIAS_DE_BORDA)
    dias = (hoje - desde).days + 1
    return max(1, min(dias, MLClient.MAX_DIAS_DE_VISITAS))


async def grava_visitas(
    pool, seller_id: uuid.UUID, item_id: str, visitas_por_dia: dict[str, int]
) -> int:
    """Grava as visitas de um item. Devolve quantos dias foram gravados.

    Dia com zero visitas NAO vira linha: ausencia ja significa zero, e gravar
    seriam dezenas de milhares de linhas sem informacao. A excecao e o dia que
    JA tem linha -- se o ML passou a reportar zero para um dia que antes tinha
    visitas, a correcao precisa chegar, senao o numero velho fica para sempre.
    """
    linhas = [
        (seller_id, item_id, date.fromisoformat(dia), int(total))
        for dia, total in sorted(visitas_por_dia.items())
        if total > 0
    ]
    zerados = [
        (seller_id, item_id, date.fromisoformat(dia), 0)
        for dia, total in sorted(visitas_por_dia.items())
        if total <= 0
    ]

    async with pool.acquire() as conn, conn.transaction():
        if linhas:
            await conn.executemany(_UPSERT_VISITAS, linhas)
        if zerados:
            # So atualiza o que ja existe; nao cria linha nova com zero.
            await conn.executemany(
                "UPDATE item_visits SET visitas = 0, colhido_em = now()"
                " WHERE seller_id=$1 AND item_id=$2 AND dia=$3",
                [(s, i, d) for s, i, d, _ in zerados],
            )
    return len(linhas)


async def colhe_visitas(
    pool,
    seller_id: uuid.UUID,
    *,
    client,
    desde_item: str | None = None,
    hoje: date | None = None,
    on_item=None,
) -> ResultadoVisitas:
    """Colhe visitas de todos os itens vendidos pelo seller.

    `desde_item` retoma do item SEGUINTE a ele — o cursor guarda o ultimo
    concluido, nao o proximo a fazer, porque "concluido" e o que se sabe com
    certeza depois de gravar.

    `on_item` e chamado depois de cada item com o item_id concluido. E por ele
    que o job salva o cursor e renova o lease: um vendedor com 50 produtos sao
    50 chamadas ao ML, e um lease de 2 minutos nao cobre isso.

    Falha de UM item nao derruba a colheita. Anuncio apagado devolve 404, e
    perder as visitas de um item nao justifica perder as dos outros 49 — o
    problema vai pros warnings do job.
    """
    itens = await itens_a_colher(pool, seller_id)
    if desde_item is not None:
        # `suppress(ValueError)`: o item do cursor pode ter sumido de
        # `order_items` entre uma tentativa e outra. Nesse caso a lista fica
        # como veio e a colheita recomeca do zero -- correto e barato, porque
        # o upsert e idempotente e o custo e so de chamadas repetidas.
        with contextlib.suppress(ValueError):
            itens = itens[itens.index(desde_item) + 1 :]

    dias_pedidos = await janela_a_pedir(pool, seller_id, hoje=hoje)
    resultado = ResultadoVisitas()

    for item_id in itens:
        try:
            visitas = client.get_item_visits(item_id, last=dias_pedidos)
        except MLAPIError as exc:
            resultado.warnings.append(f"visitas de {item_id}: HTTP {exc.status_code}")
        else:
            resultado.dias_gravados += await grava_visitas(pool, seller_id, item_id, visitas)
        resultado.itens_processados += 1
        if on_item is not None:
            await on_item(item_id, resultado.itens_processados, len(itens))

    return resultado

"""Colheita de visitas por anuncio.

O que estes testes protegem e uma propriedade que nenhum outro dado do
sistema tem: visita e PERECIVEL. A janela consultavel e de 150 dias e o
numero so consolida depois de ~48h. Errar aqui nao gera numero errado hoje --
gera buraco permanente no historico, porque o que saiu da janela nao volta.
"""

from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from backend.ml.visitas_pg import colhe_visitas, janela_a_pedir
from backend.worker import runner
from src.ml_client import MLAPIError, MLClient

from .test_worker import _job, _seller_conectado, ambiente  # noqa: F401

pytestmark = pytest.mark.asyncio

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3::timestamptz, 'paid', 100, 0, 0, 1001, '{}'::jsonb, now())
"""


class ClienteDeVisitas:
    """Cliente falso. Registra o que foi pedido e devolve o que mandarem."""

    def __init__(
        self, por_item: dict[str, dict[str, int]] | None = None, quebra: set | None = None
    ):
        self.por_item = por_item or {}
        self.quebra = quebra or set()
        self.chamadas: list[tuple[str, int]] = []

    def get_item_visits(self, item_id: str, *, last: int, ending: str | None = None):
        self.chamadas.append((item_id, last))
        if item_id in self.quebra:
            raise MLAPIError(404, "item nao encontrado")
        return self.por_item.get(item_id, {})


async def _vendeu(pool, seller_id, order_id, item_id, quando="2026-10-01T13:00:00+00:00"):
    dt = datetime.fromisoformat(quando)
    async with pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, order_id, seller_id, dt)
        await conn.execute(
            "INSERT INTO order_items (seller_id, order_id, item_id, quantity, unit_price)"
            " VALUES ($1,$2,$3,1,100)",
            seller_id,
            order_id,
            item_id,
        )


async def _visitas_gravadas(pool, seller_id, item_id=None):
    sql = "SELECT item_id, dia, visitas FROM item_visits WHERE seller_id=$1"
    args = [seller_id]
    if item_id:
        sql += " AND item_id=$2"
        args.append(item_id)
    async with pool.acquire() as conn:
        return {
            (r["item_id"], r["dia"].isoformat()): r["visitas"] for r in await conn.fetch(sql, *args)
        }


# ---------- a janela de 48h ----------


async def test_recolher_substitui_em_vez_de_somar(pg_pool, test_seller):
    """O dia colhido dentro da janela de 48h vem subcontado e e corrigido.

    E o teste central da feature. Visita e contagem FECHADA do dia, nao evento
    acumulavel: somar duplicaria o historico a cada sincronizacao, e o grafico
    de conversao subiria sozinho sem ninguem ter visitado nada.

    Mutacao: trocar o `ON CONFLICT ... DO UPDATE` por um insert simples e ver
    este teste quebrar.
    """
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1")

    # Primeira colheita: o ML ainda nao consolidou e reporta 3.
    await colhe_visitas(pg_pool, sid, client=ClienteDeVisitas({"MLB1": {"2026-10-14": 3}}))
    assert await _visitas_gravadas(pg_pool, sid) == {("MLB1", "2026-10-14"): 3}

    # Segunda colheita, ja fora da janela de 48h: o numero real era 17.
    await colhe_visitas(pg_pool, sid, client=ClienteDeVisitas({"MLB1": {"2026-10-14": 17}}))

    assert await _visitas_gravadas(pg_pool, sid) == {("MLB1", "2026-10-14"): 17}, (
        "recolher tem que SUBSTITUIR; 20 aqui significa que somou"
    )


async def test_janela_seguinte_cobre_a_borda_de_48h(pg_pool, test_seller):
    """A segunda colheita volta 2 dias, senao a subcontagem fica para sempre."""
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1")
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO item_visits (seller_id, item_id, dia, visitas) VALUES ($1,'MLB1',$2,5)",
            sid,
            date(2026, 10, 14),
        )

    dias = await janela_a_pedir(pg_pool, sid, hoje=date(2026, 10, 15))

    # De 12/10 (14 menos a borda de 2) ate 15/10, inclusive: 4 dias.
    assert dias == 4


# ---------- o teto de 150 dias ----------


async def test_primeiro_sync_pede_o_maximo_disponivel(pg_pool, test_seller):
    """Sem visita nenhuma colhida, pede 150 dias.

    Nao e exagero: o que nao for colhido agora sai da janela e some para
    sempre. E a unica chance que existe daquele periodo.
    """
    _, sid = test_seller
    assert await janela_a_pedir(pg_pool, sid) == MLClient.MAX_DIAS_DE_VISITAS


async def test_nunca_pede_mais_que_o_teto(pg_pool, test_seller):
    """Conta com um ano de historico nao pede 365 dias.

    A API recusa a chamada inteira acima de 150, e o job perderia tambem os
    150 dias validos que existiam.
    """
    _, sid = test_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO item_visits (seller_id, item_id, dia, visitas) VALUES ($1,'MLB1',$2,1)",
            sid,
            date(2025, 10, 15),
        )

    dias = await janela_a_pedir(pg_pool, sid, hoje=date(2026, 10, 15))

    assert dias == MLClient.MAX_DIAS_DE_VISITAS


async def test_o_cliente_limita_o_que_pede_a_api(monkeypatch):
    """A trava tambem existe no cliente, nao so em quem calcula a janela."""
    pedidos = {}

    class Falso(MLClient):
        def get(self, path, params=None):
            pedidos.update(params or {})
            return {"results": []}

    Falso("token").get_item_visits("MLB1", last=9999)

    assert pedidos["last"] == MLClient.MAX_DIAS_DE_VISITAS
    assert pedidos["unit"] == "day"


# ---------- ausencia nao e zero ----------


async def test_dia_sem_visita_nao_vira_linha(pg_pool, test_seller):
    """Ausencia ja significa zero; gravar seriam dezenas de milhares de linhas
    sem informacao nenhuma."""
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1")

    await colhe_visitas(
        pg_pool,
        sid,
        client=ClienteDeVisitas({"MLB1": {"2026-10-10": 4, "2026-10-11": 0, "2026-10-12": 2}}),
    )

    gravadas = await _visitas_gravadas(pg_pool, sid)
    assert gravadas == {("MLB1", "2026-10-10"): 4, ("MLB1", "2026-10-12"): 2}
    assert ("MLB1", "2026-10-11") not in gravadas


async def test_zero_corrige_um_dia_que_ja_tinha_linha(pg_pool, test_seller):
    """Se o ML passar a reportar zero para um dia que tinha visitas, a correcao
    precisa chegar -- senao o numero velho fica para sempre."""
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1")
    await colhe_visitas(pg_pool, sid, client=ClienteDeVisitas({"MLB1": {"2026-10-10": 9}}))

    await colhe_visitas(pg_pool, sid, client=ClienteDeVisitas({"MLB1": {"2026-10-10": 0}}))

    assert await _visitas_gravadas(pg_pool, sid) == {("MLB1", "2026-10-10"): 0}


# ---------- cursor e robustez ----------


async def test_cursor_retoma_do_item_seguinte(pg_pool, test_seller):
    """Um vendedor com 50 produtos sao 50 chamadas; refazer tudo e caro."""
    _, sid = test_seller
    for i, item in enumerate(["MLB1", "MLB2", "MLB3"], start=1):
        await _vendeu(pg_pool, sid, i, item)

    cliente = ClienteDeVisitas({i: {"2026-10-10": 1} for i in ["MLB1", "MLB2", "MLB3"]})
    await colhe_visitas(pg_pool, sid, client=cliente, desde_item="MLB1")

    pedidos = [item for item, _ in cliente.chamadas]
    assert pedidos == ["MLB2", "MLB3"], "MLB1 ja estava concluido no cursor"


async def test_falha_de_um_item_nao_derruba_os_outros(pg_pool, test_seller):
    """Anuncio apagado devolve 404. Perder as visitas de um item nao justifica
    perder as dos outros 49."""
    _, sid = test_seller
    for i, item in enumerate(["MLB1", "MLB2"], start=1):
        await _vendeu(pg_pool, sid, i, item)

    cliente = ClienteDeVisitas({"MLB2": {"2026-10-10": 7}}, quebra={"MLB1"})
    resultado = await colhe_visitas(pg_pool, sid, client=cliente)

    assert await _visitas_gravadas(pg_pool, sid) == {("MLB2", "2026-10-10"): 7}
    assert resultado.itens_processados == 2
    assert any("MLB1" in aviso for aviso in resultado.warnings)


async def test_visitas_de_outro_vendedor_nao_vazam(pg_pool, test_seller, outro_seller):
    _, sid = test_seller
    _, outro_sid = outro_seller
    await _vendeu(pg_pool, outro_sid, 1, "ALHEIO")
    await _vendeu(pg_pool, sid, 2, "MEU")

    await colhe_visitas(
        pg_pool,
        sid,
        client=ClienteDeVisitas({"MEU": {"2026-10-10": 3}, "ALHEIO": {"2026-10-10": 99}}),
    )

    assert await _visitas_gravadas(pg_pool, sid) == {("MEU", "2026-10-10"): 3}
    assert await _visitas_gravadas(pg_pool, outro_sid) == {}


# ---------- o job na fila ----------


async def test_delta_encadeia_um_job_de_visitas(pg_pool, test_seller):
    """`uniq_sync_job_ativo` garante UM job ativo por seller, entao enfileirar
    os dois juntos (como a spec previa) devolveria None no segundo e a
    colheita nunca aconteceria. O encadeamento e o que faz ela acontecer."""
    from .test_ingest_pg import ClienteFake

    user_id, sid = test_seller
    await _seller_conectado(pg_pool, sid)
    job = await _job(pg_pool, sid, kind="delta")

    await runner.executa_job(pg_pool, job, client=ClienteFake())

    async with pg_pool.acquire() as conn:
        kinds = [
            r["kind"]
            for r in await conn.fetch(
                "SELECT kind FROM sync_jobs WHERE seller_id=$1 ORDER BY id", sid
            )
        ]
    assert kinds == ["delta", "visitas"]


async def test_job_de_visitas_nao_mexe_em_last_synced_at(pg_pool, test_seller):
    """`last_synced_at` e a marca d'agua dos PEDIDOS, e `_delta` deriva dela a
    janela a pedir. Um job de visitas que a atualizasse faria o delta seguinte
    achar que os pedidos ja foram buscados -- e um dia de venda sumiria."""
    _, sid = test_seller
    await _seller_conectado(pg_pool, sid)
    await _vendeu(pg_pool, sid, 1, "MLB1")
    async with pg_pool.acquire() as conn:
        antes = await conn.fetchval("SELECT last_synced_at FROM sellers WHERE id=$1", sid)

    job = await _job(pg_pool, sid, kind="visitas")
    await runner.executa_job(pg_pool, job, client=ClienteDeVisitas({"MLB1": {"2026-10-10": 5}}))

    async with pg_pool.acquire() as conn:
        depois = await conn.fetchval("SELECT last_synced_at FROM sellers WHERE id=$1", sid)
    assert depois == antes


async def test_job_de_visitas_encadeia_o_frete_e_nao_a_si_mesmo(pg_pool, test_seller):
    """Visitas encadeando visitas alimentaria a fila para sempre. O proximo
    elo e o frete, que fecha a cadeia (ver `test_frete.py`)."""
    _, sid = test_seller
    await _seller_conectado(pg_pool, sid)
    await _vendeu(pg_pool, sid, 1, "MLB1")

    job = await _job(pg_pool, sid, kind="visitas")
    await runner.executa_job(pg_pool, job, client=ClienteDeVisitas({"MLB1": {"2026-10-10": 5}}))

    async with pg_pool.acquire() as conn:
        kinds = await conn.fetch("SELECT kind FROM sync_jobs WHERE seller_id=$1 ORDER BY id", sid)
    assert [k["kind"] for k in kinds] == ["visitas", "frete"]


async def test_kind_desconhecido_falha_alto(pg_pool, test_seller):
    """Antes o despacho era `if backfill ... else delta`: um kind novo caia no
    delta em silencio e ingeria pedidos sem ninguem notar."""
    _, sid = test_seller
    await _seller_conectado(pg_pool, sid)
    job = await _job(pg_pool, sid, kind="delta")
    falsificado = dict(job)
    falsificado["kind"] = "inventado"

    with pytest.raises(ValueError, match="desconhecido"):
        await runner.executa_job(pg_pool, falsificado, client=ClienteDeVisitas())


async def test_cursor_do_job_guarda_o_ultimo_item_concluido(pg_pool, test_seller):
    _, sid = test_seller
    await _seller_conectado(pg_pool, sid)
    for i, item in enumerate(["MLB1", "MLB2"], start=1):
        await _vendeu(pg_pool, sid, i, item)

    job = await _job(pg_pool, sid, kind="visitas")
    await runner.executa_job(pg_pool, job, client=ClienteDeVisitas({"MLB1": {}, "MLB2": {}}))

    async with pg_pool.acquire() as conn:
        cursor = await conn.fetchval("SELECT cursor FROM sync_jobs WHERE id=$1", job["id"])
    cursor = cursor if isinstance(cursor, dict) else json.loads(cursor)
    assert cursor["ultimo_item"] == "MLB2"


async def test_paridade_sem_visita_colhida(pg_pool, test_seller):
    """Sem nenhuma visita, nada no sistema muda de valor.

    E o teste que garante que a feature nao afeta quem ainda nao a tem.
    """
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1")

    assert await _visitas_gravadas(pg_pool, sid) == {}
    assert await janela_a_pedir(pg_pool, sid) == MLClient.MAX_DIAS_DE_VISITAS


# ---------- visitas e conversao na curva ABC ----------


async def _abc(pool, seller_id):
    from backend.analytics.segmentation_pg import abc_pareto

    df = await abc_pareto(pool, seller_id, "2026-10-01", "2026-11-01")
    return {linha["sku"]: linha for _, linha in df.iterrows()}


async def test_visitas_nao_sao_multiplicadas_pelo_numero_de_pedidos(pg_pool, test_seller):
    """A armadilha que a CTE existe pra evitar.

    Visita e por ITEM e por dia; `order_items` tem uma linha por item por
    PEDIDO. Juntar antes do GROUP BY multiplica: um produto vendido em 3
    pedidos apareceria com 3x as visitas que teve, e a conversao sairia 3
    vezes menor -- sem nada falhar, e com o numero parecendo plausivel.

    Mutacao: mover o LEFT JOIN de `item_visits` pra dentro da CTE, junto do
    `order_items`, e ver este teste quebrar.
    """
    _, sid = test_seller
    for i in range(1, 4):
        await _vendeu(pg_pool, sid, i, "MLB1", quando=f"2026-10-0{i}T13:00:00+00:00")
    await colhe_visitas(pg_pool, sid, client=ClienteDeVisitas({"MLB1": {"2026-10-05": 100}}))

    linha = (await _abc(pg_pool, sid))["MLB1"]

    assert linha["visitas"] == 100, "300 aqui significa que multiplicou pelos 3 pedidos"
    assert linha["unidades"] == 3


async def test_conversao_e_unidades_sobre_visitas(pg_pool, test_seller):
    """Rotulada "conversao (unidades)" na tela justamente por nao ser
    pedidos/visitas. Inventar o numero sem dizer qual e seria repetir o erro
    do custo estimado."""
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1")
    await colhe_visitas(pg_pool, sid, client=ClienteDeVisitas({"MLB1": {"2026-10-01": 50}}))

    linha = (await _abc(pg_pool, sid))["MLB1"]

    assert linha["visitas"] == 50
    assert linha["conversao"] == pytest.approx(2.0), "1 unidade / 50 visitas = 2%"


async def test_venda_de_antes_da_colheita_nao_entra_na_conversao(pg_pool, test_seller):
    """O ML so entrega 150 dias de visita, e o pedido vem desde o comeco.

    Num periodo que comeca antes da primeira visita colhida, a venda daqueles
    dias entrava no numerador e a visita deles, que nunca foi colhida, nao
    entrava no denominador. Medido na loja real com o historico inteiro:
    conversao de 9,2% onde a real era 7,7%.

    A unidade continua contada em `unidades` -- a venda aconteceu. So sai da
    conversao, que compara vendas e visitas dos mesmos dias.
    """
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", quando="2026-09-20T13:00:00+00:00")
    await _vendeu(pg_pool, sid, 2, "MLB1", quando="2026-10-10T13:00:00+00:00")
    await colhe_visitas(pg_pool, sid, client=ClienteDeVisitas({"MLB1": {"2026-10-05": 50}}))

    from backend.analytics.segmentation_pg import abc_pareto

    df = await abc_pareto(pg_pool, sid, "2026-09-01", "2026-11-01")
    linha = df.set_index("sku").loc["MLB1"]

    assert linha["unidades"] == 2
    assert linha["unidades_com_visita"] == 1
    assert linha["conversao"] == pytest.approx(2.0), "4% aqui e a venda de setembro inflando"


async def test_a_colheita_comeca_no_mesmo_dia_para_a_loja_inteira(pg_pool, test_seller):
    """Linha de visita so existe em dia com visita: ausencia e zero.

    Entao o primeiro dia com linha de UM anuncio nao e onde a colheita dele
    comecou -- e so o primeiro dia em que alguem o visitou. A colheita comeca
    na mesma data para a loja inteira, e e por ela que a venda e cortada.
    Aqui o MLB1 vendeu em 03/10, foi visitado so a partir de 05/10, e a venda
    conta: a colheita ja existia desde 02/10, dia que o MLB2 registrou.
    """
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1", quando="2026-10-03T13:00:00+00:00")
    await _vendeu(pg_pool, sid, 2, "MLB2", quando="2026-10-03T13:00:00+00:00")
    await colhe_visitas(
        pg_pool,
        sid,
        client=ClienteDeVisitas({"MLB1": {"2026-10-05": 50}, "MLB2": {"2026-10-02": 10}}),
    )

    linha = (await _abc(pg_pool, sid))["MLB1"]

    assert linha["unidades_com_visita"] == 1
    assert linha["conversao"] == pytest.approx(2.0)


async def test_item_nunca_colhido_vem_como_none(pg_pool, test_seller):
    """ "—" na tela, nunca 0%. Zero por cento e uma afirmacao."""
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1")

    linha = (await _abc(pg_pool, sid))["MLB1"]

    assert linha["visitas"] is None
    assert linha["conversao"] is None


async def test_item_colhido_com_zero_visitas_e_diferente_de_nao_colhido(pg_pool, test_seller):
    """Colhemos e deu zero e uma informacao; nunca colhemos nao e.

    O item tem linha de visita fora da janela, entao foi colhido -- dentro da
    janela deu zero, e isso e um fato, nao uma ausencia.
    """
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1")
    await colhe_visitas(pg_pool, sid, client=ClienteDeVisitas({"MLB1": {"2026-09-01": 12}}))

    linha = (await _abc(pg_pool, sid))["MLB1"]

    assert linha["visitas"] == 0, "colhido, e na janela deu zero"
    assert linha["conversao"] is None, "sem visita nao ha conversao pra calcular"


async def test_visitas_fora_da_janela_nao_entram(pg_pool, test_seller):
    _, sid = test_seller
    await _vendeu(pg_pool, sid, 1, "MLB1")
    await colhe_visitas(
        pg_pool,
        sid,
        client=ClienteDeVisitas({"MLB1": {"2026-09-20": 999, "2026-10-05": 40}}),
    )

    linha = (await _abc(pg_pool, sid))["MLB1"]

    assert linha["visitas"] == 40

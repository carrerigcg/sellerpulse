"""Testes do worker: fatiamento em meses, cursor e retomada."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from backend.jobs import queue
from backend.ml import tokens as tokens_mod
from backend.worker import runner
from src.auth import TokenSet

from .test_ingest_pg import ClienteFake, _pedido

ANCORA = datetime(2026, 9, 28, 12, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ML_CLIENT_ID", "1234567890")
    monkeypatch.setenv("ML_CLIENT_SECRET", "secret-do-app-ml")
    tokens_mod._fernet.cache_clear()
    yield
    tokens_mod._fernet.cache_clear()


async def _seller_conectado(pool, seller_id, ml_seller_id=987654):
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE sellers SET ml_seller_id = $2 WHERE id = $1", seller_id, ml_seller_id
        )
    await tokens_mod.PostgresTokenStore(pool, seller_id).save(
        TokenSet(
            access_token="APP_USR-valido",
            refresh_token="TG-valido",
            expires_at=datetime.now(UTC) + timedelta(hours=5),
        )
    )


async def _job(pool, seller_id, kind="backfill"):
    await queue.enqueue(pool, seller_id, kind)
    return await queue.claim_next(pool)


def test_janelas_cobrem_o_periodo_sem_furo_nem_sobreposicao():
    """Furo = pedido perdido. Sobreposicao = trabalho e rate limit jogados fora."""
    janelas = runner.janelas(ANCORA, quantidade=6)
    assert len(janelas) == 6
    assert janelas[0][0] == ANCORA - timedelta(days=180)
    assert janelas[-1][1] == ANCORA
    # strict=False de proposito: janelas[1:] e sempre 1 elemento mais curta que
    # janelas por construcao (e o par consecutivo que o teste quer comparar),
    # entao strict=True estouraria sempre, independente do resultado.
    for anterior, seguinte in zip(janelas, janelas[1:], strict=False):
        assert anterior[1] == seguinte[0]


def test_janelas_sao_deterministicas_pela_ancora():
    """A ancora e o `started_at` persistido, nao `now()`.

    Se as janelas fossem calculadas de `now()`, uma retomada meia hora depois
    deslocaria todas elas — e o cursor "3 janelas feitas" passaria a apontar
    pra um periodo diferente, deixando um furo no historico.
    """
    assert runner.janelas(ANCORA, quantidade=6) == runner.janelas(ANCORA, quantidade=6)


async def test_backfill_ingere_todas_as_janelas_e_conclui(pg_pool, test_seller):
    _u, seller_id = test_seller
    await _seller_conectado(pg_pool, seller_id)
    job = await _job(pg_pool, seller_id)
    cliente = ClienteFake()

    await runner.executa_job(pg_pool, job, client=cliente)

    assert len(cliente.chamadas_get_orders) == 12  # 6 janelas x (paid + cancelled)
    async with pg_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT status FROM sync_jobs WHERE id = $1", job["id"])
        ultimo = await conn.fetchval("SELECT last_synced_at FROM sellers WHERE id = $1", seller_id)
    assert row["status"] == "done"
    assert ultimo is not None


async def test_cursor_permite_retomar_sem_refazer(pg_pool, test_seller):
    """A instancia morreu na 3a janela: a retomada comeca da 3a, nao da 1a.

    Sem isso, um free tier que hiberna a cada 15 min poderia nunca terminar o
    backfill de um seller com volume alto — ele recomecaria para sempre.
    """
    _u, seller_id = test_seller
    await _seller_conectado(pg_pool, seller_id)
    job = await _job(pg_pool, seller_id)

    class ClienteQueQuebra(ClienteFake):
        def get_orders(self, **kw):
            if len(self.chamadas_get_orders) >= 4:  # quebra na 3a janela
                raise RuntimeError("instancia hibernou")
            return super().get_orders(**kw)

    with pytest.raises(RuntimeError):
        await runner.executa_job(pg_pool, job, client=ClienteQueQuebra())

    async with pg_pool.acquire() as conn:
        cursor = await conn.fetchval("SELECT cursor FROM sync_jobs WHERE id = $1", job["id"])
    assert json.loads(cursor)["janelas_concluidas"] == 2

    # Retomada: pega o mesmo job (lease vencido) e continua.
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE sync_jobs SET leased_until = now() - interval '1 minute' WHERE id = $1",
            job["id"],
        )
    repescado = await queue.claim_next(pg_pool)
    cliente2 = ClienteFake()
    await runner.executa_job(pg_pool, repescado, client=cliente2)

    # 4 janelas restantes x 2 status = 8 chamadas. Se refizesse tudo, seriam 12.
    assert len(cliente2.chamadas_get_orders) == 8

    # A contagem sozinha nao pega o bug de calcular a ancora de `now()`: o
    # numero de janelas restantes (6 - cursor) e o mesmo nos dois casos, so a
    # DATA muda. Este assert compara a 3a janela pedida com o `started_at`
    # persistido do job — e o que de fato prova que a retomada nao pulou nem
    # repetiu periodo nenhum.
    esperado = runner.janelas(repescado["started_at"])[2]
    assert cliente2.chamadas_get_orders[0]["de"] == esperado[0].isoformat()
    assert cliente2.chamadas_get_orders[0]["ate"] == esperado[1].isoformat()


async def test_delta_usa_date_last_updated_e_janela_curta(pg_pool, test_seller):
    _u, seller_id = test_seller
    await _seller_conectado(pg_pool, seller_id)
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "UPDATE sellers SET last_synced_at = now() - interval '10 hours' WHERE id = $1",
            seller_id,
        )
    job = await _job(pg_pool, seller_id, kind="delta")
    cliente = ClienteFake()

    await runner.executa_job(pg_pool, job, client=cliente)

    assert len(cliente.chamadas_get_orders) == 2  # uma janela so
    assert all(c["campo"] == "date_last_updated" for c in cliente.chamadas_get_orders)


async def test_warnings_do_ingest_chegam_no_job(pg_pool, test_seller):
    _u, seller_id = test_seller
    await _seller_conectado(pg_pool, seller_id)
    job = await _job(pg_pool, seller_id, kind="delta")
    cliente = ClienteFake(paid=[_pedido(1, item_id="MLB_INEXISTENTE")], items={})

    await runner.executa_job(pg_pool, job, client=cliente)

    async with pg_pool.acquire() as conn:
        warnings = await conn.fetchval("SELECT warnings FROM sync_jobs WHERE id = $1", job["id"])
    assert "MLB_INEXISTENTE" in warnings


async def test_job_de_seller_sem_conexao_falha(pg_pool, test_seller):
    """Seller sem ml_seller_id: estoura antes de tentar usar token nenhum."""
    _u, seller_id = test_seller
    job = await _job(pg_pool, seller_id)
    with pytest.raises(RuntimeError, match="sem conta"):
        await runner.executa_job(pg_pool, job)


# ---------------------------------------------------------------------------
# Renovacao de lease DENTRO da janela.
#
# Medido na ingestao real: backfill de 6 janelas em 706s = 118s por janela,
# contra `LEASE_SEGUNDOS = 120`. O heartbeat batia uma vez por janela, ANTES de
# `ingest_janela`, entao todo o enriquecimento N+1 (uma chamada ao ML por item
# novo) rodava sem renovacao. Dois segundos de margem e sorte: numa loja um
# pouco maior o lease vence no meio da janela e o job casa com `_CANDIDATO`
# (`status = 'running' AND leased_until < now()`) enquanto ainda esta rodando.
# ---------------------------------------------------------------------------

ITEMS_FAKE = {"MLB1": {"title": "Fone", "category_id": "MLB1055"}}


def _espia_heartbeat(monkeypatch, pool):
    """Anota cada `queue.heartbeat`, SEM substituir o real.

    O espiao chama o heartbeat de verdade e depois le `leased_until` do banco —
    e isso que permite afirmar que o lease andou, e nao apenas que uma funcao
    foi chamada.
    """
    real = queue.heartbeat
    registros: list[dict] = []

    async def espiao(p, job_id, *, fase, processados, total):
        await real(p, job_id, fase=fase, processados=processados, total=total)
        async with pool.acquire() as conn:
            leased = await conn.fetchval("SELECT leased_until FROM sync_jobs WHERE id = $1", job_id)
        registros.append({"fase": fase, "leased_until": leased})

    monkeypatch.setattr(runner.queue, "heartbeat", espiao)
    return registros


def _renovacoes(registros):
    """Só as renovações vindas de dentro da janela.

    A `fase` delas carrega o contador de pedidos entre parenteses
    ("Baixando 2026-04-01 a 2026-05-01 (3/5)"); as de janela e a de conclusao
    nao tem parenteses nenhum.
    """
    return [r for r in registros if "(" in r["fase"]]


async def test_lease_e_renovado_dentro_da_janela(pg_pool, test_seller, monkeypatch):
    """O lease anda NO MEIO de uma janela, nao so entre janelas."""
    _u, seller_id = test_seller
    await _seller_conectado(pg_pool, seller_id)
    job = await _job(pg_pool, seller_id)
    # O intervalo real e LEASE_SEGUNDOS / 4 = 30s e o teste nao pode esperar
    # isso. Aqui o que se prova e o fio ligado; que o throttle vale e o teste
    # seguinte, que roda com o intervalo de produção.
    monkeypatch.setattr(runner, "INTERVALO_HEARTBEAT", 0.0)
    registros = _espia_heartbeat(monkeypatch, pg_pool)

    cliente = ClienteFake(paid=[_pedido(1), _pedido(2), _pedido(3)], items=ITEMS_FAKE)
    await runner.executa_job(pg_pool, job, client=cliente)

    assert _renovacoes(registros), (
        "nenhuma renovacao de dentro da janela: on_progress nao foi ligado"
    )

    # Prova que foi DENTRO de uma janela: existe renovacao entre o heartbeat que
    # abriu a 1a janela e o que abriu a 2a.
    aberturas = [i for i, r in enumerate(registros) if r["fase"].startswith("Baixando")]
    aberturas = [i for i in aberturas if "(" not in registros[i]["fase"]]
    assert len(aberturas) == 6, [r["fase"] for r in registros]
    entre = _renovacoes(registros[aberturas[0] + 1 : aberturas[1]])
    assert entre, "as renovacoes sairam so entre janelas, nao durante a ingestao de uma"

    # E o que importa de fato: `leased_until` no banco ficou mais longe do que
    # estava quando a janela comecou.
    assert entre[-1]["leased_until"] > registros[aberturas[0]]["leased_until"]


async def test_renovacao_de_lease_e_throttled(pg_pool, test_seller, monkeypatch):
    """Renovar por pedido seriam 1.017 UPDATEs extras no Supabase por backfill.

    Roda com o `INTERVALO_HEARTBEAT` de produção de proposito: uma janela que
    termina em menos de 30s nao tem por que renovar nada — o heartbeat de
    abertura ja vale 120s.
    """
    _u, seller_id = test_seller
    await _seller_conectado(pg_pool, seller_id)
    job = await _job(pg_pool, seller_id, kind="delta")  # uma janela so
    registros = _espia_heartbeat(monkeypatch, pg_pool)

    pedidos = [_pedido(i) for i in range(1, 31)]
    await runner.executa_job(pg_pool, job, client=ClienteFake(paid=pedidos, items=ITEMS_FAKE))

    renovacoes = _renovacoes(registros)
    assert len(renovacoes) <= 1, (
        f"{len(renovacoes)} renovacoes para {len(pedidos)} pedidos ingeridos em "
        f"muito menos que INTERVALO_HEARTBEAT ({runner.INTERVALO_HEARTBEAT}s): "
        "o throttle nao esta valendo e cada pedido virou um UPDATE"
    )


async def test_delta_tambem_renova_o_lease(pg_pool, test_seller, monkeypatch):
    """O delta e UMA janela: sem o on_progress, a unica renovacao e a inicial.

    E o caminho que roda a cada sync manual, e `MARGEM_DELTA` + dias sem sync
    fazem a janela render pedido suficiente pra passar dos 2 minutos.
    """
    _u, seller_id = test_seller
    await _seller_conectado(pg_pool, seller_id)
    job = await _job(pg_pool, seller_id, kind="delta")
    monkeypatch.setattr(runner, "INTERVALO_HEARTBEAT", 0.0)
    registros = _espia_heartbeat(monkeypatch, pg_pool)

    cliente = ClienteFake(paid=[_pedido(1), _pedido(2)], items=ITEMS_FAKE)
    await runner.executa_job(pg_pool, job, client=cliente)

    renovacoes = _renovacoes(registros)
    assert renovacoes, "o delta nao renova o lease durante a janela"
    # A fase que o usuario le continua sendo a da janela, com o progresso somado.
    assert all(r["fase"].startswith("Buscando atualizacoes (") for r in renovacoes)


async def test_falha_ao_renovar_lease_nao_mata_a_ingestao(pg_pool, test_seller, monkeypatch):
    """Heartbeat e bookkeeping; a janela em andamento vale mais que ele.

    Propagando, a excecao sairia de dentro do loop de pedidos de `ingest_janela`
    (o try/except de la cobre so a persistencia do pedido) e abortaria uma janela
    que estava correta — gastando uma das 3 tentativas do job por causa de um
    UPDATE de progresso. O pior caso de engolir e o lease vencer, que e
    justamente o cenario que a fila ja trata.
    """
    _u, seller_id = test_seller
    await _seller_conectado(pg_pool, seller_id)
    job = await _job(pg_pool, seller_id, kind="delta")
    monkeypatch.setattr(runner, "INTERVALO_HEARTBEAT", 0.0)

    real = queue.heartbeat

    async def heartbeat_que_quebra_na_renovacao(p, job_id, *, fase, processados, total):
        if "(" in fase:  # so as renovacoes de dentro da janela
            raise RuntimeError("banco fora do ar ao renovar o lease")
        return await real(p, job_id, fase=fase, processados=processados, total=total)

    monkeypatch.setattr(runner.queue, "heartbeat", heartbeat_que_quebra_na_renovacao)

    cliente = ClienteFake(paid=[_pedido(1), _pedido(2)], items=ITEMS_FAKE)
    await runner.executa_job(pg_pool, job, client=cliente)

    async with pg_pool.acquire() as conn:
        status = await conn.fetchval("SELECT status FROM sync_jobs WHERE id = $1", job["id"])
        pedidos = await conn.fetchval("SELECT count(*) FROM orders WHERE seller_id = $1", seller_id)
    assert status == "done", "a falha no heartbeat derrubou o job"
    assert pedidos == 2, "a falha no heartbeat descartou pedidos ja ingeridos"


async def test_loop_consome_e_para_quando_sinalizado(pg_pool, test_seller):
    """O loop processa o que esta na fila e encerra no evento de parada.

    Sem o `parar`, a task do lifespan nao terminaria no shutdown e o Render
    mataria o container a forca a cada deploy.
    """
    import asyncio

    _u, seller_id = test_seller
    await _seller_conectado(pg_pool, seller_id)
    await queue.enqueue(pg_pool, seller_id, "delta")

    parar = asyncio.Event()
    tarefa = asyncio.create_task(
        runner.loop(pg_pool, parar=parar, client_factory=lambda _t: ClienteFake())
    )

    # Espera o job sair da fila, com teto pra nao pendurar a suite.
    for _ in range(100):
        await asyncio.sleep(0.05)
        async with pg_pool.acquire() as conn:
            status = await conn.fetchval(
                "SELECT status FROM sync_jobs WHERE seller_id = $1", seller_id
            )
        if status == "done":
            break

    parar.set()
    await asyncio.wait_for(tarefa, timeout=5)
    assert status == "done", f"job nao foi consumido (status={status})"
    assert tarefa.done()


async def test_loop_sobrevive_a_falha_no_registro_de_erro(pg_pool, test_seller, monkeypatch):
    """Se `queue.fail` estourar, o loop NAO pode morrer.

    Ele e a unica coisa que consome a fila e ninguem o reinicia: uma excecao
    escapando daqui para a sincronizacao de TODOS os sellers em silencio, sem
    crash e sem log, ate o proximo deploy.
    """
    import asyncio

    _u, seller_id = test_seller
    await _seller_conectado(pg_pool, seller_id)
    await queue.enqueue(pg_pool, seller_id, "delta")

    def _cliente_que_quebra(_job):
        class Quebrado(ClienteFake):
            def get_orders(self, **kw):
                raise RuntimeError("erro no job")

        return Quebrado()

    chamadas_fail = []

    async def _fail_que_quebra(*args, **kwargs):
        chamadas_fail.append(args)
        raise RuntimeError("banco fora do ar ao registrar a falha")

    monkeypatch.setattr(runner.queue, "fail", _fail_que_quebra)

    parar = asyncio.Event()
    tarefa = asyncio.create_task(
        runner.loop(pg_pool, parar=parar, client_factory=_cliente_que_quebra)
    )
    # Tempo pra pegar o job, falhar, e tentar registrar a falha.
    for _ in range(40):
        await asyncio.sleep(0.05)
        if chamadas_fail:
            break

    parar.set()
    await asyncio.wait_for(tarefa, timeout=5)

    assert chamadas_fail, "o loop nem chegou a tentar registrar a falha"
    assert tarefa.done()
    assert tarefa.exception() is None, "o loop morreu em vez de sobreviver"

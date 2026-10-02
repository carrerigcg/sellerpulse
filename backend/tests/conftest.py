# backend/tests/conftest.py
from __future__ import annotations

import os
import uuid

import asyncpg
import pytest

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sellerpulse_test"
)


@pytest.fixture(autouse=True, scope="session")
def _suite_nunca_fala_com_producao():
    """Garante que NENHUM teste desta suite alcance o banco de producao.

    A exposicao nao e de uma feature, e do import: `backend/main.py` roda
    `load_dotenv(backend/.env)` no topo do modulo, e esse arquivo guarda o
    `DATABASE_URL` e o `DEMO_SELLER_ID` de PRODUCAO. `backend/db.py` le
    `os.environ["DATABASE_URL"]` na HORA da chamada, nao no import -- entao
    qualquer teste que suba o `lifespan` e esqueca o
    `monkeypatch.setenv("DATABASE_URL", ...)` abre pool contra producao, sem
    nenhum aviso. Isso e um `pytest` numa maquina de dev escrevendo no banco
    que serve cliente pago.

    Quem le isso tende a pensar so no refresh da demo, por causa do
    `DELETE FROM orders`. O buraco e maior: `worker_habilitado()` continua
    OPT-OUT (de proposito -- ver `backend/main.py`), entao o mesmo esquecimento
    sobe o `worker_loop` contra producao, drenando a fila de verdade e
    renovando tokens de verdade. Fixar o `DATABASE_URL` aqui fecha os dois de
    uma vez, e fecha tambem o proximo consumidor de `DATABASE_URL` que alguem
    adicionar sem lembrar desta armadilha.

    As tres travas:

    1. `DATABASE_URL` fixado em `TEST_DATABASE_URL`. O `load_dotenv` do import
       pode ate injetar o valor de producao durante a coleta -- esta fixture
       roda depois dele e antes do primeiro corpo de teste, e como `db.py` le
       a variavel na hora da chamada, o valor que vale em tempo de execucao e
       sempre este. Quem reimportar ou recarregar o `main` no meio da suite
       tambem nao reverte nada: `load_dotenv` nao sobrescreve variavel ja
       presente no ambiente.
    2. `DEMO_SELLER_ID` removido. Se algo ligar o refresh, ele degrada pro
       no-op `sem-env` em vez de mirar no seller de producao.
    3. `DEMO_REFRESH_IN_PROCESS=0` explicito. Com o default agora opt-in (ver
       `demo_refresh_habilitado`), essa linha e redundante -- e fica de
       proposito: o default protege quem ESQUECE a variavel, nao quem a tem
       setada, e `backend/.env` e um arquivo nao versionado onde um dev pode
       deixar `=1` pra testar producao local. Com `os.environ` tendo
       precedencia sobre o `load_dotenv`, zerar aqui e o que impede que o
       default da suite dependa de um arquivo que ninguem revisa. Custa uma
       linha; cobre o caso em que o default sozinho nao cobriria.

    Quem precisa do caminho LIGADO liga com `monkeypatch.setenv`, que tem
    precedencia dentro do teste e e revertido no teardown.
    """
    anteriores = {
        chave: os.environ.get(chave)
        for chave in ("DATABASE_URL", "DEMO_SELLER_ID", "DEMO_REFRESH_IN_PROCESS")
    }
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ.pop("DEMO_SELLER_ID", None)
    os.environ["DEMO_REFRESH_IN_PROCESS"] = "0"
    yield
    for chave, anterior in anteriores.items():
        if anterior is None:
            os.environ.pop(chave, None)
        else:
            os.environ[chave] = anterior


@pytest.fixture
async def pg_pool():
    # server_settings espelha backend/db.py: sem UTC fixo, o Postgres local
    # (America/Sao_Paulo) daria resultados diferentes da producao (UTC).
    pool = await asyncpg.create_pool(
        TEST_DATABASE_URL, min_size=1, max_size=2, server_settings={"timezone": "UTC"}
    )
    yield pool
    await pool.close()


@pytest.fixture
async def test_seller(pg_pool):
    """Cria um auth.users + sellers de teste, devolve (user_id, seller_id).

    O DELETE no teardown cascateia pra sellers e todas as tabelas analíticas
    (FK com ON DELETE CASCADE), então cada teste começa limpo.
    """
    user_id = uuid.uuid4()
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO auth.users (id, email) VALUES ($1, $2)", user_id, "teste@sellerpulse.dev"
        )
        seller_id = await conn.fetchval(
            "INSERT INTO sellers (user_id) VALUES ($1) RETURNING id", user_id
        )
    yield user_id, seller_id
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM auth.users WHERE id = $1", user_id)


@pytest.fixture
async def outro_seller(pg_pool):
    """Segundo seller — usado pra provar isolamento entre tenants."""
    user_id = uuid.uuid4()
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO auth.users (id, email) VALUES ($1, $2)", user_id, "outro@sellerpulse.dev"
        )
        seller_id = await conn.fetchval(
            "INSERT INTO sellers (user_id) VALUES ($1) RETURNING id", user_id
        )
    yield user_id, seller_id
    async with pg_pool.acquire() as conn:
        await conn.execute("DELETE FROM auth.users WHERE id = $1", user_id)


@pytest.fixture
async def pg_pool_fuso_nao_utc():
    """Pool com TimeZone de sessao DELIBERADAMENTE nao-UTC.

    `to_char` sobre `timestamptz` converte pro fuso da SESSAO. As queries
    analiticas usam `AT TIME ZONE 'UTC'` justamente pra nao depender disso —
    mas `pg_pool` fixa UTC, entao remover o `AT TIME ZONE` do codigo nao
    quebraria teste nenhum (verificado por mutacao). Este pool existe pra
    fechar essa cegueira: rodar a mesma query nos dois pools tem que dar o
    MESMO resultado.

    America/Sao_Paulo (UTC-3) e escolhido explicitamente em vez de herdar o
    fuso do SO pra que o teste seja deterministico em qualquer maquina —
    inclusive numa CI que rode em UTC, onde herdar tornaria o teste vazio.
    """
    pool = await asyncpg.create_pool(
        TEST_DATABASE_URL,
        min_size=1,
        max_size=2,
        server_settings={"timezone": "America/Sao_Paulo"},
    )
    yield pool
    await pool.close()


@pytest.fixture
async def pg_pool_concorrente():
    """Pool com DUAS conexoes fisicas ja abertas antes do teste comecar.

    Existe pra fechar um falso positivo de mutacao. O `pg_pool` normal abre com
    `min_size=1`: numa corrida entre duas corrotinas, a primeira pega a conexao
    ociosa na hora e a segunda tem que abrir uma conexao nova (TCP + handshake
    de autenticacao do Postgres). Esse handshake demora mais que a secao critica
    inteira da primeira — entao a segunda chega quando o trabalho ja terminou e
    commitou, e o teste de concorrencia passa IGUAL com ou sem o lock. Quem
    serializava as duas era latencia de conexao, nao `FOR UPDATE` (verificado
    empiricamente: 5/5 verdes com o lock removido).

    Com `min_size=2`, as duas conexoes existem antes da corrida e a disputa pela
    linha e real: sem o lock, as duas renovam o token.
    """
    pool = await asyncpg.create_pool(
        TEST_DATABASE_URL, min_size=2, max_size=2, server_settings={"timezone": "UTC"}
    )
    yield pool
    await pool.close()

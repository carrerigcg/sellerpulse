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
def _refresh_da_demo_desligado_por_padrao():
    """Desliga o refresh da demo em TODA a suite, por padrao.

    `backend/main.py` roda `load_dotenv(backend/.env)` no import, e esse arquivo
    guarda o `DEMO_SELLER_ID` de PRODUCAO. O refresh executa
    `DELETE FROM orders WHERE seller_id = $1` -- entao um teste de lifespan que
    esquecesse de apontar `DATABASE_URL` pro banco de teste regeneraria a demo
    publica de verdade. A trava `is_demo` nao pegaria esse caso: o seller de
    producao E uma demo, ela protege contra apagar um cliente real, nao contra
    apontar pro banco errado.

    Desligar aqui torna a escolha explicita: quem testa o refresh LIGA com
    `monkeypatch.setenv`, que tem precedencia dentro do teste. O default da
    suite passa a ser o seguro, em vez de depender de cada teste lembrar.
    """
    anterior = os.environ.get("DEMO_REFRESH_IN_PROCESS")
    os.environ["DEMO_REFRESH_IN_PROCESS"] = "0"
    yield
    if anterior is None:
        os.environ.pop("DEMO_REFRESH_IN_PROCESS", None)
    else:
        os.environ["DEMO_REFRESH_IN_PROCESS"] = anterior


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

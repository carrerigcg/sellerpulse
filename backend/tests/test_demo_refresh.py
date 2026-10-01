# backend/tests/test_demo_refresh.py
"""Testes do refresh do seller de demonstracao.

O valor esta concentrado em dois lugares: a trava `is_demo` (o que vem depois
dela e um DELETE nos pedidos do seller) e a prova de que o refresh de fato
MOVE as datas -- um refresh que falha em silencio e indistinguivel de um que
funciona, olhando so pro retorno.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.demo_refresh import (
    DIAS_PARA_VENCER,
    SEMANAS_DEMO,
    regenera_demo,
    regenera_demo_se_vencida,
)
from backend.seed import seed_postgres
from src.demo_data import ANCHOR_DATE, DEFAULT_SEED, generate_catalog, generate_orders

# Parametros pequenos pra manter os testes rapidos, iguais aos de test_seed.py.
# `weeks_back` tem que ser o MESMO nas duas semeaduras de um teste de refresh:
# com a mesma seed e a mesma quantidade de semanas, os `order_id` gerados
# coincidem exatamente -- que e o cenario onde o `ON CONFLICT DO NOTHING`
# transformaria o refresh em no-op. Mudar `weeks_back` entre as chamadas
# esconderia o bug.
_PEQUENO = {"n_categories": 5, "n_products": 10, "weeks_back": 2, "claim_rate": 0.04}

_TABELAS = ("categories_cache", "items_cache", "orders", "order_items", "claims")

_DEMO_DB = Path(__file__).resolve().parents[2] / "data" / "demo.db"


async def _marca_demo(pg_pool, seller_id) -> None:
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET is_demo = true WHERE id = $1", seller_id)


async def _max_date_closed(pg_pool, seller_id) -> datetime | None:
    async with pg_pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT max(date_closed) FROM orders WHERE seller_id = $1", seller_id
        )


async def _contagens(pg_pool, seller_id) -> dict[str, int]:
    async with pg_pool.acquire() as conn:
        return {
            tabela: await conn.fetchval(
                f"SELECT count(*) FROM {tabela} WHERE seller_id = $1", seller_id
            )
            for tabela in _TABELAS
        }


# --------------------------------------------------------------------------
# 1. A trava
# --------------------------------------------------------------------------


async def test_recusa_seller_sem_marca_de_demo_e_preserva_os_pedidos(pg_pool, test_seller):
    """A linha mais importante do modulo: sem `is_demo`, nao apaga nada.

    Conferir so o `raises` nao bastaria -- o que importa e que os pedidos do
    seller continuem lá. E conferir so as CONTAGENS tambem nao bastaria: o
    refresh usa a mesma seed, entao uma versao sem a trava apagaria tudo e
    reinseriria a mesma quantidade de linhas, com as contagens batendo. O que
    denuncia a troca e a DATA -- semeamos com a ancora congelada e pedimos o
    refresh com `now()`.
    """
    _, sid = test_seller
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, anchor=ANCHOR_DATE, **_PEQUENO)
    antes = await _contagens(pg_pool, sid)
    data_antes = await _max_date_closed(pg_pool, sid)
    assert all(n > 0 for n in antes.values())

    with pytest.raises(ValueError, match="is_demo"):
        await regenera_demo(pg_pool, sid, anchor=datetime.now(UTC), **_PEQUENO)

    assert await _contagens(pg_pool, sid) == antes
    assert await _max_date_closed(pg_pool, sid) == data_antes


async def test_recusa_seller_inexistente_sem_apagar_o_vizinho(pg_pool, test_seller):
    """`is_demo` NULL (seller que nao existe) tem que levantar tambem.

    `if not marcado` sozinho trataria None e False igual, mas a mensagem
    precisa distinguir: "nao existe" e um id errado, "nao e demo" e um id de
    cliente real. Os dados do seller legitimo ao lado continuam intactos.
    """
    _, sid = test_seller
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, anchor=ANCHOR_DATE, **_PEQUENO)
    antes = await _contagens(pg_pool, sid)
    data_antes = await _max_date_closed(pg_pool, sid)

    with pytest.raises(ValueError, match="nao existe"):
        await regenera_demo(pg_pool, uuid.uuid4(), anchor=datetime.now(UTC), **_PEQUENO)

    assert await _contagens(pg_pool, sid) == antes
    assert await _max_date_closed(pg_pool, sid) == data_antes


# --------------------------------------------------------------------------
# 2. O refresh move as datas de verdade
# --------------------------------------------------------------------------


async def test_refresh_move_as_datas_para_a_nova_ancora(pg_pool, test_seller):
    """O teste mais importante do arquivo.

    Semeia com a ancora velha, regenera com uma nova, e exige que
    `max(date_closed)` tenha ANDADO. Sem o DELETE em `regenera_demo`, os
    `order_id` reaparecem identicos (derivam do RNG, nao das datas), todo
    INSERT cai no `ON CONFLICT DO NOTHING` e o refresh reporta sucesso sem
    mudar uma linha -- falha invisivel em producao, que e justamente a que
    este teste existe pra pegar.
    """
    _, sid = test_seller
    await _marca_demo(pg_pool, sid)
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, anchor=ANCHOR_DATE, **_PEQUENO)

    antigo = await _max_date_closed(pg_pool, sid)
    assert antigo is not None
    contagens_antes = await _contagens(pg_pool, sid)

    nova_ancora = datetime.now(UTC)
    await regenera_demo(pg_pool, sid, anchor=nova_ancora, seed=DEFAULT_SEED, **_PEQUENO)

    novo = await _max_date_closed(pg_pool, sid)
    assert novo is not None
    assert novo > antigo, "o refresh nao moveu as datas (DELETE ausente? ON CONFLICT engoliu?)"
    # O pedido mais novo cai ~1 dia antes da ancora; o pior caso do RNG e ~7
    # dias (ver DIAS_PARA_VENCER em backend/demo_refresh.py).
    assert nova_ancora - novo < timedelta(days=DIAS_PARA_VENCER)

    # Refresh substitui, nao acumula: sem o DELETE as contagens dobrariam, e
    # com um DELETE incompleto alguma tabela ficaria maior que antes.
    assert await _contagens(pg_pool, sid) == contagens_antes


async def test_refresh_nao_deixa_order_items_orfao(pg_pool, test_seller):
    """`order_items` nao e apagada explicitamente -- quem a leva e o cascade
    da FK `(seller_id, order_id) references orders`. Se esse cascade deixasse
    de valer, sobrariam itens apontando pra pedido que nao existe mais."""
    _, sid = test_seller
    await _marca_demo(pg_pool, sid)
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, anchor=ANCHOR_DATE, **_PEQUENO)
    await regenera_demo(pg_pool, sid, anchor=datetime.now(UTC), seed=DEFAULT_SEED, **_PEQUENO)

    async with pg_pool.acquire() as conn:
        orfaos = await conn.fetchval(
            """
            SELECT count(*) FROM order_items oi
            WHERE oi.seller_id = $1
              AND NOT EXISTS (
                  SELECT 1 FROM orders o
                  WHERE o.seller_id = oi.seller_id AND o.order_id = oi.order_id
              )
            """,
            sid,
        )
    assert orfaos == 0


# --------------------------------------------------------------------------
# 3. Atomicidade
# --------------------------------------------------------------------------


async def test_falha_depois_do_delete_nao_esvazia_a_demo(pg_pool, test_seller):
    """Uma falha no meio tem que devolver o dado ANTIGO, nao uma demo vazia.

    A falha e injetada por parametro, sem tocar em codigo de producao:
    `n_categories` acima da lista curada faz `generate_catalog` levantar --
    e ele e chamado DEPOIS dos DELETEs, dentro da transacao.
    """
    _, sid = test_seller
    await _marca_demo(pg_pool, sid)
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, anchor=ANCHOR_DATE, **_PEQUENO)
    antes = await _contagens(pg_pool, sid)
    data_antes = await _max_date_closed(pg_pool, sid)

    with pytest.raises(ValueError, match="n_categories"):
        await regenera_demo(
            pg_pool,
            sid,
            anchor=datetime.now(UTC),
            seed=DEFAULT_SEED,
            n_categories=99,
            n_products=10,
            weeks_back=2,
            claim_rate=0.04,
        )

    assert await _contagens(pg_pool, sid) == antes
    assert await _max_date_closed(pg_pool, sid) == data_antes


async def test_falha_depois_dos_inserts_desfaz_tudo(pg_pool, test_seller, monkeypatch):
    """Variante mais dura: a falha acontece com TODAS as linhas novas ja
    inseridas, so faltando o commit.

    Monkeypatcha `_contagens` (chamada por `seed_na_conexao` no fim, depois de
    todos os INSERTs) pra levantar. O rollback tem que devolver exatamente o
    dado antigo -- nem vazio, nem uma mistura dos dois conjuntos.
    """
    import backend.seed as seed_mod

    _, sid = test_seller
    await _marca_demo(pg_pool, sid)
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, anchor=ANCHOR_DATE, **_PEQUENO)
    antes = await _contagens(pg_pool, sid)
    data_antes = await _max_date_closed(pg_pool, sid)

    real = seed_mod._contagens
    chamadas = {"n": 0}

    async def _contagens_que_falha_no_fim(conn, seller_id):
        chamadas["n"] += 1
        if chamadas["n"] >= 2:
            raise RuntimeError("falha simulada depois dos INSERTs")
        return await real(conn, seller_id)

    monkeypatch.setattr(seed_mod, "_contagens", _contagens_que_falha_no_fim)

    with pytest.raises(RuntimeError, match="falha simulada"):
        await regenera_demo(pg_pool, sid, anchor=datetime.now(UTC), seed=DEFAULT_SEED, **_PEQUENO)

    assert await _contagens(pg_pool, sid) == antes
    assert await _max_date_closed(pg_pool, sid) == data_antes


# --------------------------------------------------------------------------
# 4. O gatilho de validade
# --------------------------------------------------------------------------


async def test_dado_fresco_nao_dispara_regeneracao(pg_pool, test_seller, monkeypatch):
    """Demo recem-semeada nao deve ser regenerada a cada cold start."""
    _, sid = test_seller
    await _marca_demo(pg_pool, sid)
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, anchor=datetime.now(UTC), **_PEQUENO)
    antes = await _max_date_closed(pg_pool, sid)
    contagens_antes = await _contagens(pg_pool, sid)
    monkeypatch.setenv("DEMO_SELLER_ID", str(sid))

    assert await regenera_demo_se_vencida(pg_pool) == "atual"

    # Nao basta confiar no status: se a regeneracao tivesse rodado, as
    # contagens subiriam pras 26 semanas e a data mudaria.
    assert await _max_date_closed(pg_pool, sid) == antes
    assert await _contagens(pg_pool, sid) == contagens_antes


async def test_dado_velho_dispara_regeneracao_ate_hoje(pg_pool, test_seller, monkeypatch):
    """Demo congelada na ancora antiga tem que ser regenerada ate hoje.

    Roda o caminho REAL (`SEMANAS_DEMO` semanas, catalogo cheio), porque e
    exatamente isso que vai rodar no cold start do Render.
    """
    _, sid = test_seller
    await _marca_demo(pg_pool, sid)
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, anchor=ANCHOR_DATE, **_PEQUENO)
    antes = await _max_date_closed(pg_pool, sid)
    monkeypatch.setenv("DEMO_SELLER_ID", str(sid))

    agora = datetime.now(UTC)
    assert await regenera_demo_se_vencida(pg_pool) == "regenerada"

    novo = await _max_date_closed(pg_pool, sid)
    assert novo > antes
    assert agora - novo < timedelta(days=DIAS_PARA_VENCER)

    # Profundidade: 26 semanas tem que cobrir ~180 dias de historico, a mesma
    # janela do backfill de um seller real.
    async with pg_pool.acquire() as conn:
        mais_antigo = await conn.fetchval(
            "SELECT min(date_closed) FROM orders WHERE seller_id = $1", sid
        )
    assert (novo - mais_antigo) > timedelta(days=SEMANAS_DEMO * 7 - 14)


async def test_sem_pedido_nenhum_tambem_dispara(pg_pool, test_seller, monkeypatch):
    """`max(date_closed)` NULL (demo marcada mas nunca semeada) conta como
    vencida -- senao a demo publica ficaria vazia pra sempre."""
    _, sid = test_seller
    await _marca_demo(pg_pool, sid)
    monkeypatch.setenv("DEMO_SELLER_ID", str(sid))

    assert await regenera_demo_se_vencida(pg_pool) == "regenerada"
    assert await _max_date_closed(pg_pool, sid) is not None


# --------------------------------------------------------------------------
# 5. Determinismo preservado
# --------------------------------------------------------------------------


def test_ancora_default_continua_batendo_com_o_demo_db_commitado() -> None:
    """`generate_orders` sem `anchor` tem que reproduzir `data/demo.db`.

    O arquivo e versionado e o golden do PDF depende destes numeros. Se o
    default do parametro novo tivesse virado `now()` -- ou se a ancora
    congelada tivesse mudado de valor -- este teste cai, em vez de o commit de
    `data/demo.db` virar "always dirty" e o golden do PDF quebrar depois.
    """
    assert _DEMO_DB.exists(), f"demo.db versionado nao encontrado em {_DEMO_DB}"
    conn = sqlite3.connect(str(_DEMO_DB))
    try:
        do_arquivo = conn.execute("SELECT order_id, date_closed FROM orders ORDER BY order_id")
        do_arquivo = do_arquivo.fetchall()
    finally:
        conn.close()

    # Mesmos parametros que `generate_demo_db` usa.
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=10, n_products=50)
    gerados = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=12)
    do_gerador = sorted((o["order_id"], o["date_closed"]) for o in gerados)

    assert do_gerador == do_arquivo


def test_passar_a_ancora_congelada_explicitamente_da_o_mesmo_resultado() -> None:
    """`anchor=ANCHOR_DATE` explicito == omitir o parametro.

    Prova que o parametro novo esta de fato ligado ao default, e nao que o
    default sobreviveu por o corpo da funcao ainda usar a constante direto.
    """
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=5, n_products=10)
    sem = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=2)
    com = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=2, anchor=ANCHOR_DATE)
    assert sem == com


def test_ancora_diferente_muda_as_datas_mas_nao_os_order_ids() -> None:
    """A premissa que torna o DELETE obrigatorio, fixada em teste.

    Se um dia `order_id` passar a derivar das datas, o `ON CONFLICT DO
    NOTHING` do seed voltaria a servir de refresh -- e este teste avisa que a
    justificativa do DELETE mudou.
    """
    catalog = generate_catalog(seed=DEFAULT_SEED, n_categories=5, n_products=10)
    antiga = generate_orders(catalog=catalog, seed=DEFAULT_SEED, weeks_back=2)
    nova = generate_orders(
        catalog=catalog,
        seed=DEFAULT_SEED,
        weeks_back=2,
        anchor=ANCHOR_DATE + timedelta(days=90),
    )
    assert [o["order_id"] for o in antiga] == [o["order_id"] for o in nova]
    assert [o["date_closed"] for o in antiga] != [o["date_closed"] for o in nova]


# --------------------------------------------------------------------------
# 6. Ambiente nao configurado e no-op, nunca excecao
# --------------------------------------------------------------------------


async def test_sem_env_var_e_no_op(pg_pool, monkeypatch):
    """API sem demo configurada e o caso normal em dev e na CI."""
    monkeypatch.delenv("DEMO_SELLER_ID", raising=False)
    assert await regenera_demo_se_vencida(pg_pool) == "sem-env"


async def test_env_var_invalida_e_no_op(pg_pool, monkeypatch):
    monkeypatch.setenv("DEMO_SELLER_ID", "nao-e-uuid")
    assert await regenera_demo_se_vencida(pg_pool) == "env-invalida"


async def test_seller_inexistente_e_no_op(pg_pool, monkeypatch):
    """Diferente de `regenera_demo`, o gatilho NAO levanta aqui: derrubar o
    boot da API por causa de uma demo nao semeada seria trocar um problema
    cosmetico por indisponibilidade."""
    monkeypatch.setenv("DEMO_SELLER_ID", str(uuid.uuid4()))
    assert await regenera_demo_se_vencida(pg_pool) == "seller-ausente"


async def test_seller_sem_marca_de_demo_e_no_op_e_preserva_os_pedidos(
    pg_pool, test_seller, monkeypatch
):
    """Um typo na env var apontando pra cliente real: no-op, e sem apagar nada.

    Este e o pior cenario do deploy. O gatilho checa `is_demo` ANTES de chamar
    `regenera_demo` -- se ele chamasse direto, a trava ainda levantaria, mas
    dentro de uma task de fundo isso viraria um traceback no log em vez de um
    no-op deliberado.
    """
    _, sid = test_seller
    await seed_postgres(pg_pool, sid, seed=DEFAULT_SEED, anchor=ANCHOR_DATE, **_PEQUENO)
    antes = await _contagens(pg_pool, sid)
    monkeypatch.setenv("DEMO_SELLER_ID", str(sid))

    assert await regenera_demo_se_vencida(pg_pool) == "nao-e-demo"
    assert await _contagens(pg_pool, sid) == antes

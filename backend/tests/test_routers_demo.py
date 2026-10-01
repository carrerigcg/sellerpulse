"""Testes dos endpoints publicos de demonstracao."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.main import app
from backend.routers._common import MAX_JANELA_DIAS, MAX_N

from .conftest import TEST_DATABASE_URL

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3, 'paid', $4, 0, 0, 1, '{}'::jsonb, now())
"""

# Variante com buyer_id explicito -- os testes de RFM precisam de compradores
# distintos (a _INSERT_ORDER acima fixa buyer_id=1 pra todo mundo).
_INSERT_ORDER_COM_COMPRADOR = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3, 'paid', $4, 0, 0, $5, '{}'::jsonb, now())
"""

_INSERT_ITEM_CACHE = """
    INSERT INTO items_cache (seller_id, item_id, title, category_id, fetched_at)
    VALUES ($1, $2, $3, 'C1', now())
"""

_INSERT_ORDER_ITEM = """
    INSERT INTO order_items (seller_id, order_id, item_id, quantity, unit_price)
    VALUES ($1, $2, $3, 1, $4)
"""


def _ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "irrelevante-aqui")
    # O lifespan valida a chave de cifra no boot desde a Task 11.
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WORKER_IN_PROCESS", "0")
    # Sem isto o lifespan sobe o refresh da demo, que comeca com
    # `DELETE FROM orders WHERE seller_id = ...` -- no seller que estes testes
    # marcam como demo e acabaram de popular com datas fixas. A task
    # apagaria as linhas conferidas aqui no meio do teste.
    monkeypatch.setenv("DEMO_REFRESH_IN_PROCESS", "0")


@pytest.fixture
async def client_demo(monkeypatch, pg_pool, test_seller):
    _u, seller_id = test_seller
    async with pg_pool.acquire() as conn:
        await conn.execute("UPDATE sellers SET is_demo = true WHERE id = $1", seller_id)
    _ambiente(monkeypatch)
    monkeypatch.setenv("DEMO_SELLER_ID", str(seller_id))
    with TestClient(app) as c:
        yield c, seller_id


async def test_demo_responde_sem_autenticacao(client_demo, pg_pool):
    """Zero atrito e o ponto: recrutador e prospect veem o produto sem cadastro."""
    client, seller_id = client_demo
    async with pg_pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, 1, seller_id, datetime(2026, 7, 15, tzinfo=UTC), 250.0)
    resp = client.get(
        "/demo/fluxo-financeiro", params={"date_from": "2026-07-01", "date_to": "2026-08-01"}
    )
    assert resp.status_code == 200
    assert resp.json()[0]["receita_bruta"] == 250.0


async def test_demo_ignora_seller_id_vindo_do_cliente(client_demo, pg_pool, outro_seller):
    """A porta publica nao pode virar leitura arbitraria de tenant.

    Se o endpoint aceitasse seller_id por parametro, qualquer pessoa na
    internet leria o faturamento de qualquer vendedor cadastrado.
    """
    client, seller_id = client_demo
    _ub, seller_b = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, 1, seller_id, datetime(2026, 7, 15, tzinfo=UTC), 100.0)
        await conn.execute(_INSERT_ORDER, 2, seller_b, datetime(2026, 7, 16, tzinfo=UTC), 999.0)
    resp = client.get(
        "/demo/fluxo-financeiro",
        params={"date_from": "2026-07-01", "date_to": "2026-08-01", "seller_id": str(seller_b)},
    )
    receitas = [d["receita_bruta"] for d in resp.json()]
    assert 999.0 not in receitas
    assert receitas == [100.0]


def test_demo_router_so_expoe_leitura():
    """Nenhuma rota de escrita pode existir neste router — invariante, nao URL.

    A versao anterior deste teste mandava POST numa rota e esperava 405, o que
    so prova que o FastAPI sabe rotear. Nao pegaria um POST novo adicionado
    neste arquivo em OUTRO caminho — que e exatamente como a trava se perderia.
    """
    from backend.routers import demo as router_demo

    permitidos = {"GET", "HEAD"}
    for rota in router_demo.router.routes:
        metodos = set(getattr(rota, "methods", set()))
        assert metodos <= permitidos, f"{rota.path} expoe {metodos - permitidos}"


def test_demo_manda_cache_control(client_demo):
    """Publico e igual pra todo mundo: cachear protege o free tier de abuso."""
    client, _sid = client_demo
    resp = client.get(
        "/demo/fluxo-financeiro", params={"date_from": "2026-07-01", "date_to": "2026-08-01"}
    )
    assert "max-age" in resp.headers.get("cache-control", "")


def test_demo_sem_configuracao_devolve_503(monkeypatch):
    """Ambiente sem demo configurada nao pode derrubar o resto da API."""
    _ambiente(monkeypatch)
    monkeypatch.delenv("DEMO_SELLER_ID", raising=False)
    with TestClient(app) as c:
        resp = c.get(
            "/demo/fluxo-financeiro", params={"date_from": "2026-07-01", "date_to": "2026-08-01"}
        )
        # O resto da API continua de pe.
        assert c.get("/health").status_code == 200
    assert resp.status_code == 503


def test_demo_valida_a_janela(client_demo):
    client, _sid = client_demo
    resp = client.get(
        "/demo/fluxo-financeiro", params={"date_from": "ontem", "date_to": "2026-08-01"}
    )
    assert resp.status_code == 400


async def test_demo_top_produtos(client_demo, pg_pool):
    client, seller_id = client_demo
    async with pg_pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, 1, seller_id, datetime(2026, 7, 15, tzinfo=UTC), 100.0)
        await conn.execute(
            "INSERT INTO categories_cache (seller_id, category_id, name, fetched_at) "
            "VALUES ($1, 'C1', 'Categoria', now())",
            seller_id,
        )
        await conn.execute(
            "INSERT INTO items_cache (seller_id, item_id, title, category_id, fetched_at) "
            "VALUES ($1, 'MLB1', 'Produto', 'C1', now())",
            seller_id,
        )
        await conn.execute(
            "INSERT INTO order_items (seller_id, order_id, item_id, quantity, unit_price) "
            "VALUES ($1, 1, 'MLB1', 1, 100.0)",
            seller_id,
        )
    resp = client.get(
        "/demo/top-produtos", params={"date_from": "2026-07-01", "date_to": "2026-08-01"}
    )
    assert resp.status_code == 200
    # `top_produtos` (backend/analytics/metrics_pg.py) devolve a coluna
    # "title", nao "titulo" — a mesma usada pelo /metrics/top-produtos
    # autenticado. Corrigido aqui pra nao travar num nome de coluna que nao
    # existe.
    assert resp.json()["produtos"][0]["title"] == "Produto"


async def test_demo_recusa_seller_nao_marcado_como_demo(monkeypatch, pg_pool, outro_seller):
    """Um typo no DEMO_SELLER_ID derruba a demo em vez de vazar cliente real.

    Este e o pior cenario do sistema inteiro: a unica porta sem autenticacao
    apontando pro seller errado serviria o faturamento de um cliente de
    verdade pra internet, com Cache-Control publico mandando um CDN guardar.
    A marca no banco e o que transforma isso em 503.
    """
    _u, seller_nao_demo = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount, "
            "marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at) "
            "VALUES (1, $1, now(), 'paid', 9999, 0, 0, 1, '{}'::jsonb, now())",
            seller_nao_demo,
        )
    _ambiente(monkeypatch)
    monkeypatch.setenv("DEMO_SELLER_ID", str(seller_nao_demo))

    with TestClient(app) as c:
        # A janela era 2026-01-01 -> 2027-01-01 (365 dias). Encurtada porque
        # `validate_window` passou a ter teto de duracao: com 365 dias isto
        # viraria 400 na validacao e nunca exercitaria a trava do is_demo, que e
        # o que o teste existe pra provar.
        resp = c.get(
            "/demo/fluxo-financeiro", params={"date_from": "2026-01-01", "date_to": "2026-11-01"}
        )
    assert resp.status_code == 503
    assert "9999" not in resp.text, "faturamento do seller vazou na resposta"


async def test_demo_recusa_seller_inexistente(monkeypatch, pg_pool):
    """UUID valido que nao existe no banco tambem nao serve."""
    import uuid as _uuid

    _ambiente(monkeypatch)
    monkeypatch.setenv("DEMO_SELLER_ID", str(_uuid.uuid4()))
    with TestClient(app) as c:
        resp = c.get(
            "/demo/fluxo-financeiro", params={"date_from": "2026-07-01", "date_to": "2026-08-01"}
        )
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# /demo/abc, /demo/rfm, /demo/cohort -- Checkpoint 2 da Sprint 3.
#
# Mesmas quatro garantias que /demo/fluxo-financeiro e /demo/top-produtos ja
# tem, replicadas aqui pros tres endpoints novos: sao elas que tornam uma
# porta sem autenticacao segura em vez de um buraco.
# ---------------------------------------------------------------------------


async def test_demo_abc_responde_sem_autenticacao(client_demo, pg_pool):
    client, seller_id = client_demo
    async with pg_pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, 1, seller_id, datetime(2026, 7, 15, tzinfo=UTC), 100.0)
        await conn.execute(_INSERT_ITEM_CACHE, seller_id, "MLB1", "Produto")
        await conn.execute(_INSERT_ORDER_ITEM, seller_id, 1, "MLB1", 100.0)
    resp = client.get("/demo/abc", params={"date_from": "2026-07-01", "date_to": "2026-08-01"})
    assert resp.status_code == 200
    assert resp.json()[0]["titulo"] == "Produto"


async def test_demo_abc_ignora_seller_id_vindo_do_cliente(client_demo, pg_pool, outro_seller):
    client, seller_id = client_demo
    _ub, seller_b = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, 1, seller_id, datetime(2026, 7, 15, tzinfo=UTC), 100.0)
        await conn.execute(_INSERT_ITEM_CACHE, seller_id, "MLB1", "Produto A")
        await conn.execute(_INSERT_ORDER_ITEM, seller_id, 1, "MLB1", 100.0)

        await conn.execute(_INSERT_ORDER, 2, seller_b, datetime(2026, 7, 16, tzinfo=UTC), 999.0)
        await conn.execute(_INSERT_ITEM_CACHE, seller_b, "MLB2", "Produto B")
        await conn.execute(_INSERT_ORDER_ITEM, seller_b, 2, "MLB2", 999.0)
    resp = client.get(
        "/demo/abc",
        params={"date_from": "2026-07-01", "date_to": "2026-08-01", "seller_id": str(seller_b)},
    )
    titulos = [linha["titulo"] for linha in resp.json()]
    assert titulos == ["Produto A"]
    assert "Produto B" not in titulos


async def test_demo_abc_recusa_seller_nao_marcado_como_demo(monkeypatch, pg_pool, outro_seller):
    _u, seller_nao_demo = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            _INSERT_ORDER, 1, seller_nao_demo, datetime(2026, 7, 15, tzinfo=UTC), 9999.0
        )
        await conn.execute(_INSERT_ITEM_CACHE, seller_nao_demo, "MLB9", "Produto Sigiloso")
        await conn.execute(_INSERT_ORDER_ITEM, seller_nao_demo, 1, "MLB9", 9999.0)
    _ambiente(monkeypatch)
    monkeypatch.setenv("DEMO_SELLER_ID", str(seller_nao_demo))

    with TestClient(app) as c:
        resp = c.get("/demo/abc", params={"date_from": "2026-07-01", "date_to": "2026-08-01"})
    assert resp.status_code == 503
    assert "Sigiloso" not in resp.text, "catalogo do seller vazou na resposta"


def test_demo_abc_manda_cache_control(client_demo):
    client, _sid = client_demo
    resp = client.get("/demo/abc", params={"date_from": "2026-07-01", "date_to": "2026-08-01"})
    assert "max-age" in resp.headers.get("cache-control", "")


async def test_demo_rfm_responde_sem_autenticacao(client_demo, pg_pool):
    client, seller_id = client_demo
    async with pg_pool.acquire() as conn:
        await conn.execute(
            _INSERT_ORDER_COM_COMPRADOR, 1, seller_id, datetime(2026, 7, 15, tzinfo=UTC), 250.0, 1
        )
    resp = client.get("/demo/rfm", params={"date_from": "2026-07-01", "date_to": "2026-08-01"})
    assert resp.status_code == 200
    assert resp.json()[0]["monetary"] == 250.0


async def test_demo_rfm_ignora_seller_id_vindo_do_cliente(client_demo, pg_pool, outro_seller):
    client, seller_id = client_demo
    _ub, seller_b = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            _INSERT_ORDER_COM_COMPRADOR, 1, seller_id, datetime(2026, 7, 15, tzinfo=UTC), 100.0, 1
        )
        await conn.execute(
            _INSERT_ORDER_COM_COMPRADOR, 2, seller_b, datetime(2026, 7, 16, tzinfo=UTC), 999.0, 2
        )
    resp = client.get(
        "/demo/rfm",
        params={"date_from": "2026-07-01", "date_to": "2026-08-01", "seller_id": str(seller_b)},
    )
    monetarios = [linha["monetary"] for linha in resp.json()]
    assert 999.0 not in monetarios
    assert monetarios == [100.0]


async def test_demo_rfm_recusa_seller_nao_marcado_como_demo(monkeypatch, pg_pool, outro_seller):
    _u, seller_nao_demo = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            _INSERT_ORDER_COM_COMPRADOR,
            1,
            seller_nao_demo,
            datetime(2026, 7, 15, tzinfo=UTC),
            9999.0,
            1,
        )
    _ambiente(monkeypatch)
    monkeypatch.setenv("DEMO_SELLER_ID", str(seller_nao_demo))

    with TestClient(app) as c:
        resp = c.get("/demo/rfm", params={"date_from": "2026-07-01", "date_to": "2026-08-01"})
    assert resp.status_code == 503
    assert "9999" not in resp.text, "faturamento do seller vazou na resposta"


def test_demo_rfm_manda_cache_control(client_demo):
    client, _sid = client_demo
    resp = client.get("/demo/rfm", params={"date_from": "2026-07-01", "date_to": "2026-08-01"})
    assert "max-age" in resp.headers.get("cache-control", "")


async def test_demo_cohort_responde_sem_autenticacao(client_demo, pg_pool):
    client, seller_id = client_demo
    async with pg_pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, 1, seller_id, datetime(2026, 7, 15, tzinfo=UTC), 100.0)
        await conn.execute(_INSERT_ORDER_ITEM, seller_id, 1, "MLB1", 100.0)
    resp = client.get("/demo/cohort", params={"date_from": "2026-07-01", "date_to": "2026-08-01"})
    assert resp.status_code == 200
    assert resp.json()[0]["mes_lancamento"] == "2026-07"
    assert resp.json()[0]["2026-07"] == 100.0


async def test_demo_cohort_ignora_seller_id_vindo_do_cliente(client_demo, pg_pool, outro_seller):
    client, seller_id = client_demo
    _ub, seller_b = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, 1, seller_id, datetime(2026, 7, 15, tzinfo=UTC), 100.0)
        await conn.execute(_INSERT_ORDER_ITEM, seller_id, 1, "MLB1", 100.0)

        await conn.execute(_INSERT_ORDER, 2, seller_b, datetime(2026, 7, 16, tzinfo=UTC), 999.0)
        await conn.execute(_INSERT_ORDER_ITEM, seller_b, 2, "MLB2", 999.0)
    resp = client.get(
        "/demo/cohort",
        params={"date_from": "2026-07-01", "date_to": "2026-08-01", "seller_id": str(seller_b)},
    )
    linhas = resp.json()
    assert len(linhas) == 1
    assert linhas[0]["2026-07"] == 100.0


async def test_demo_cohort_recusa_seller_nao_marcado_como_demo(monkeypatch, pg_pool, outro_seller):
    _u, seller_nao_demo = outro_seller
    async with pg_pool.acquire() as conn:
        await conn.execute(
            _INSERT_ORDER, 1, seller_nao_demo, datetime(2026, 7, 15, tzinfo=UTC), 9999.0
        )
        await conn.execute(_INSERT_ORDER_ITEM, seller_nao_demo, 1, "MLB9", 9999.0)
    _ambiente(monkeypatch)
    monkeypatch.setenv("DEMO_SELLER_ID", str(seller_nao_demo))

    with TestClient(app) as c:
        resp = c.get("/demo/cohort", params={"date_from": "2026-07-01", "date_to": "2026-08-01"})
    assert resp.status_code == 503
    assert "9999" not in resp.text, "faturamento do seller vazou na resposta"


def test_demo_cohort_manda_cache_control(client_demo):
    client, _sid = client_demo
    resp = client.get("/demo/cohort", params={"date_from": "2026-07-01", "date_to": "2026-08-01"})
    assert "max-age" in resp.headers.get("cache-control", "")


async def test_demo_cohort_janela_vazia_devolve_lista_vazia(client_demo):
    """Mesmo caso vazio do /segmentation/cohort autenticado (segmentation.py):

    cohort_produto devolve um DataFrame sem index nomeado quando nao ha
    vendas -- reset_index() estouraria uma coluna "index" espuria em vez do
    formato de lista vazia que o cliente espera.
    """
    client, _sid = client_demo
    resp = client.get("/demo/cohort", params={"date_from": "2020-01-01", "date_to": "2020-02-01"})
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Limites de entrada (backend/routers/_common.py).
#
# A trava 3 do modulo (Cache-Control publico) so protege o free tier enquanto a
# chave de cache for estavel: como a chave inclui date_from/date_to, variar as
# datas a cada request gera chave nova toda vez e fura o cache dos DOIS lados
# (max-age da resposta e revalidate de 1h da Vercel). Sem teto de janela, um
# loop trivial mantem a instancia do Render acordada de graca e queima a cota
# mensal. Testado aqui porque /demo e a porta sem autenticacao, mas o validador
# e o mesmo dos routers autenticados -- de proposito, pros dois caminhos nao
# divergirem.
# ---------------------------------------------------------------------------

_INICIO = date(2026, 7, 1)


def _janela(dias: int) -> dict[str, str]:
    """Params de uma janela de exatamente `dias` dias, derivada do teto."""
    return {
        "date_from": _INICIO.isoformat(),
        "date_to": (_INICIO + timedelta(days=dias)).isoformat(),
    }


@pytest.mark.parametrize(
    "params",
    [
        {"date_from": "2026-08-01", "date_to": "2026-07-01"},  # invertida
        {"date_from": "2026-07-01", "date_to": "2026-07-01"},  # duracao zero
    ],
    ids=["invertida", "duracao-zero"],
)
def test_demo_recusa_janela_nao_ordenada(client_demo, params):
    """Janela invertida devolvia 200 com lista vazia.

    O dashboard mostra lista vazia como "nenhuma venda no periodo" -- que e
    indistinguivel de um periodo ruim de verdade, quando a verdade e que o
    cliente pediu nada. Erro de entrada tem que ser dito como erro de entrada.
    """
    client, _sid = client_demo
    resp = client.get("/demo/fluxo-financeiro", params=params)
    assert resp.status_code == 400, resp.text
    assert "anterior" in resp.json()["detail"]


def test_demo_recusa_janela_longa_demais(client_demo):
    client, _sid = client_demo
    resp = client.get("/demo/fluxo-financeiro", params=_janela(MAX_JANELA_DIAS + 1))
    assert resp.status_code == 400, resp.text
    assert str(MAX_JANELA_DIAS) in resp.json()["detail"]


def test_demo_recusa_janela_de_dois_seculos(client_demo):
    """A sondagem concreta da auditoria: parseia, logo era aceita.

    `1900-01-01` a `2100-01-01` passava pela validacao antiga (as duas datas sao
    ISO 8601 validas) e virava uma chave de cache nova a cada variacao.
    """
    client, _sid = client_demo
    resp = client.get(
        "/demo/fluxo-financeiro", params={"date_from": "1900-01-01", "date_to": "2100-01-01"}
    )
    assert resp.status_code == 400, resp.text


def test_demo_aceita_a_janela_maxima(client_demo):
    """Borda de dentro: exatamente o teto ainda e 200, nao 400 nem 500."""
    client, _sid = client_demo
    resp = client.get("/demo/fluxo-financeiro", params=_janela(MAX_JANELA_DIAS))
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("dias", [1, 83, 90], ids=["minima", "demo-semeada", "padrao-frontend"])
def test_demo_aceita_as_janelas_dos_callers_reais(client_demo, dias):
    """As janelas que existem de verdade continuam passando.

    90 dias e o `periodoPadrao()` de toda tela (autenticada e publica), e e
    tambem a duracao que `janelaAnterior` repete pra comparacao -- ela nunca
    soma as duas. 83 dias e o intervalo da base de demo semeada (2026-05-09 a
    2026-07-31). 1 dia e a janela mais curta que ainda faz sentido.
    """
    client, _sid = client_demo
    resp = client.get("/demo/fluxo-financeiro", params=_janela(dias))
    assert resp.status_code == 200, resp.text


def test_demo_recusa_n_acima_do_teto(client_demo):
    """`n` sem teto e `LIMIT` arbitrario: trabalho ilimitado por request."""
    client, _sid = client_demo
    resp = client.get("/demo/top-produtos", params={**_janela(30), "n": MAX_N + 1})
    assert resp.status_code == 400, resp.text
    assert str(MAX_N) in resp.json()["detail"]


def test_demo_aceita_n_no_teto(client_demo):
    """Borda de dentro do `n`."""
    client, _sid = client_demo
    resp = client.get("/demo/top-produtos", params={**_janela(30), "n": MAX_N})
    assert resp.status_code == 200, resp.text

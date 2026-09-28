"""Testes dos endpoints publicos de demonstracao."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.main import app

from .conftest import TEST_DATABASE_URL

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3, 'paid', $4, 0, 0, 1, '{}'::jsonb, now())
"""


def _ambiente(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "irrelevante-aqui")
    # O lifespan valida a chave de cifra no boot desde a Task 11.
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("WORKER_IN_PROCESS", "0")


@pytest.fixture
def client_demo(monkeypatch, test_seller):
    _u, seller_id = test_seller
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


def test_demo_nao_aceita_escrita(client_demo):
    client, _sid = client_demo
    assert client.post("/demo/fluxo-financeiro").status_code == 405
    assert client.delete("/demo/fluxo-financeiro").status_code == 405


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

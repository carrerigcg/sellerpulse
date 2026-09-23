from __future__ import annotations

import time
from datetime import UTC, datetime

import jwt
import pytest
from fastapi.testclient import TestClient

from backend.main import app

from .conftest import TEST_DATABASE_URL

TEST_JWT_SECRET = "test-secret-do-supabase"

_INSERT_ORDER = """
    INSERT INTO orders (order_id, seller_id, date_closed, status, total_amount,
                        marketplace_fee, shipping_cost, buyer_id, raw_json, fetched_at)
    VALUES ($1, $2, $3::timestamptz, $4, $5, $6, $7, $8, '{}'::jsonb, now())
"""


def _make_token(user_id: str, *, expired: bool = False, secret: str = TEST_JWT_SECRET) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "exp": now - 10 if expired else now + 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


async def _order(pool, seller_id, order_id, date_closed, total, fee=0.0, ship=0.0,
                  status="paid", buyer_id=1001):
    dt = datetime.fromisoformat(date_closed)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    async with pool.acquire() as conn:
        await conn.execute(_INSERT_ORDER, order_id, seller_id, dt, status,
                            total, fee, ship, buyer_id)


async def _item(pool, seller_id, item_id, title, category_id="CAT1", category_name="Categoria 1"):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO categories_cache (seller_id, category_id, name, fetched_at) "
            "VALUES ($1,$2,$3,now()) ON CONFLICT DO NOTHING",
            seller_id, category_id, category_name)
        await conn.execute(
            "INSERT INTO items_cache (seller_id, item_id, title, category_id, fetched_at) "
            "VALUES ($1,$2,$3,$4,now()) ON CONFLICT DO NOTHING",
            seller_id, item_id, title, category_id)


async def _order_item(pool, seller_id, order_id, item_id, qty, unit_price):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO order_items (seller_id, order_id, item_id, quantity, unit_price) "
            "VALUES ($1,$2,$3,$4,$5)",
            seller_id, order_id, item_id, qty, unit_price)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    with TestClient(app) as c:
        yield c


def _auth(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(str(user_id))}"}


# ---------- caminho feliz ----------

async def test_fluxo_financeiro_endpoint(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 10.0, 5.0)
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["date"] == "2026-07-25"
    assert body[0]["receita_bruta"] == pytest.approx(100.0)


async def test_top_produtos_endpoint(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto 1")
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 10.0, 5.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 2, 50.0)
    resp = client.get(
        "/metrics/top-produtos",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "produtos" in body
    assert "categorias" in body
    assert body["produtos"][0]["item_id"] == "MLB1"


async def test_top_produtos_respeita_parametro_n(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto 1")
    await _item(pg_pool, sid, "MLB2", "Produto 2")
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 10.0, 5.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 2, 50.0)
    await _order_item(pg_pool, sid, 1, "MLB2", 1, 30.0)
    resp = client.get(
        "/metrics/top-produtos",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26", "n": 1},
        headers=_auth(user_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["produtos"]) == 1


async def test_abc_endpoint(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto 1")
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 0.0, 0.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 2, 50.0)
    resp = client.get(
        "/segmentation/abc",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["sku"] == "MLB1"
    # unico produto -> acumula 100% da receita -> classe C (nao <=80, nao <=95)
    assert body[0]["classe"] == "C"


async def test_rfm_endpoint(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 0.0, 0.0, buyer_id=1001)
    resp = client.get(
        "/segmentation/rfm",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["buyer_id"] == 1001


async def test_cohort_endpoint(client, pg_pool, test_seller):
    user_id, sid = test_seller
    await _item(pg_pool, sid, "MLB1", "Produto 1")
    await _order(pg_pool, sid, 1, "2026-07-25T10:00:00+00:00", 100.0, 0.0, 0.0)
    await _order_item(pg_pool, sid, 1, "MLB1", 2, 50.0)
    resp = client.get(
        "/segmentation/cohort",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert body[0]["mes_lancamento"] == "2026-07"


async def test_cohort_vazio_devolve_lista_vazia(client, test_seller):
    user_id, _sid = test_seller
    resp = client.get(
        "/segmentation/cohort",
        params={"date_from": "2026-01-01", "date_to": "2026-01-02"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 200
    assert resp.json() == []


# ---------- autenticação ----------

def test_sem_token_devolve_401(client):
    """HTTPBearer sem Authorization: confirmado rodando que devolve 401
    nesta versao do FastAPI (0.141.1), nao 403 como em versoes antigas."""
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26"},
    )
    assert resp.status_code == 401


def test_token_invalido_devolve_401(client):
    token = _make_token("11111111-1111-1111-1111-111111111111", secret="secret-errado")
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


# ---------- isolamento entre tenants ----------

async def test_fluxo_financeiro_isola_por_tenant(client, pg_pool, test_seller, outro_seller):
    user_a, sid_a = test_seller
    _user_b, sid_b = outro_seller
    await _order(pg_pool, sid_a, 1, "2026-07-25T10:00:00+00:00", 100.0, 0.0, 0.0)
    await _order(pg_pool, sid_b, 2, "2026-07-25T10:00:00+00:00", 999.0, 0.0, 0.0)
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26"},
        headers=_auth(user_a),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["receita_bruta"] == pytest.approx(100.0)


async def test_top_produtos_isola_por_tenant(client, pg_pool, test_seller, outro_seller):
    user_a, sid_a = test_seller
    _user_b, sid_b = outro_seller
    await _item(pg_pool, sid_a, "MLB1", "Produto A")
    await _item(pg_pool, sid_b, "MLB1", "Produto B")
    await _order(pg_pool, sid_a, 1, "2026-07-25T10:00:00+00:00", 100.0, 0.0, 0.0)
    await _order_item(pg_pool, sid_a, 1, "MLB1", 1, 10.0)
    await _order(pg_pool, sid_b, 2, "2026-07-25T10:00:00+00:00", 100.0, 0.0, 0.0)
    await _order_item(pg_pool, sid_b, 2, "MLB1", 1, 9999.0)
    resp = client.get(
        "/metrics/top-produtos",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26"},
        headers=_auth(user_a),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["produtos"]) == 1
    assert body["produtos"][0]["title"] == "Produto A"
    assert body["produtos"][0]["receita"] == pytest.approx(10.0)


# ---------- validação de entrada ----------

def test_date_from_malformada_devolve_400(client, test_seller):
    user_id, _sid = test_seller
    resp = client.get(
        "/metrics/fluxo-financeiro",
        params={"date_from": "nao-e-uma-data", "date_to": "2026-07-26"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 400


def test_date_to_malformada_devolve_400(client, test_seller):
    user_id, _sid = test_seller
    resp = client.get(
        "/segmentation/abc",
        params={"date_from": "2026-07-25", "date_to": "nao-e-uma-data"},
        headers=_auth(user_id),
    )
    assert resp.status_code == 400


@pytest.mark.parametrize("n", [0, -1])
def test_n_invalido_devolve_400(client, test_seller, n):
    user_id, _sid = test_seller
    resp = client.get(
        "/metrics/top-produtos",
        params={"date_from": "2026-07-25", "date_to": "2026-07-26", "n": n},
        headers=_auth(user_id),
    )
    assert resp.status_code == 400

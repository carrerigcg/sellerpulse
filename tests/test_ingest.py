"""Testes de src/ingest.py — orquestração do backfill."""

from __future__ import annotations

import sqlite3  # noqa: F401  # used in subsequent tasks

import pytest  # noqa: F401  # used in subsequent tasks
import responses

from src.ingest import IngestResult, ingest_last_6_months
from src.ml_client import MLClient
from src.session_store import create_session_db


def _mock_ml_endpoints(
    *,
    orders_paid=None,
    orders_cancelled=None,
    items=None,
    categories=None,
    claims=None,
):
    """Registra respostas ML no responses activate scope. Passe listas prontas."""
    orders_paid = orders_paid or []
    orders_cancelled = orders_cancelled or []
    items = items or {}
    categories = categories or {}
    claims = claims or []

    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/orders/search",
        json={"results": orders_paid, "paging": {"total": len(orders_paid)}},
        match=[responses.matchers.query_param_matcher({}, strict_match=False)],
    )
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/orders/search",
        json={"results": orders_cancelled, "paging": {"total": len(orders_cancelled)}},
    )
    for item_id, item in items.items():
        responses.add(
            responses.GET,
            f"https://api.mercadolibre.com/items/{item_id}",
            json=item,
        )
    for cat_id, cat in categories.items():
        responses.add(
            responses.GET,
            f"https://api.mercadolibre.com/categories/{cat_id}",
            json=cat,
        )
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/post-purchase/v1/claims/search",
        json={"data": claims},
    )


@responses.activate
def test_ingest_calls_all_phases_in_order_and_persists():
    _mock_ml_endpoints(
        orders_paid=[
            {
                "id": 1001,
                "date_closed": "2026-06-01T10:00:00.000-03:00",
                "date_created": "2026-06-01T10:00:00.000-03:00",
                "status": "paid",
                "total_amount": 150.0,
                "payments": [{"marketplace_fee": 15.0}],
                "shipping": {"list_cost": 10.0},
                "buyer": {"id": 42},
                "order_items": [{"item": {"id": "MLB111"}, "quantity": 1, "unit_price": 150.0}],
            },
        ],
        items={"MLB111": {"id": "MLB111", "title": "Produto Teste", "category_id": "MLB1001"}},
        categories={"MLB1001": {"id": "MLB1001", "name": "Categoria X"}},
        claims=[
            {
                "id": 500001,
                "resource_id": 1001,  # same order_id as the paid order above
                "status": "opened",
                "date_created": "2026-06-05T14:00:00.000-03:00",
            },
        ],
    )
    client = MLClient(access_token="token-fake")
    conn = create_session_db()
    result = ingest_last_6_months(client=client, seller_id=999, conn=conn)
    assert isinstance(result, IngestResult)
    assert result.total_orders == 1
    assert result.distinct_items == 1
    assert result.distinct_buyers == 1
    stored_orders = conn.execute("SELECT order_id, status FROM orders").fetchall()
    assert [(row[0], row[1]) for row in stored_orders] == [(1001, "paid")]
    stored_items = conn.execute("SELECT item_id, title FROM items_cache").fetchall()
    assert [(row[0], row[1]) for row in stored_items] == [("MLB111", "Produto Teste")]
    assert result.total_claims == 1
    stored_claims = conn.execute("SELECT claim_id, order_id, status FROM claims").fetchall()
    assert [(row[0], row[1], row[2]) for row in stored_claims] == [(500001, 1001, "opened")]
    conn.close()


@responses.activate
def test_ingest_progress_callback_fired_per_phase():
    _mock_ml_endpoints()  # tudo vazio
    client = MLClient(access_token="tok")
    conn = create_session_db()
    fases_vistas: list[str] = []
    ingest_last_6_months(
        client=client,
        seller_id=1,
        conn=conn,
        on_progress=lambda fase, _a, _t: fases_vistas.append(fase),
    )
    assert "Baixando pedidos pagos" in fases_vistas
    assert "Baixando pedidos cancelados" in fases_vistas
    assert "Baixando reclamações" in fases_vistas
    assert "Concluído" in fases_vistas
    conn.close()


@responses.activate
def test_ingest_handles_zero_orders_gracefully():
    _mock_ml_endpoints()  # tudo vazio
    client = MLClient(access_token="tok")
    conn = create_session_db()
    result = ingest_last_6_months(client=client, seller_id=1, conn=conn)
    assert result.total_orders == 0
    assert result.distinct_items == 0
    assert result.distinct_buyers == 0
    assert result.warnings == []
    conn.close()


@responses.activate
def test_ingest_item_enrichment_failure_preserves_order(monkeypatch):
    """Item enrichment falha → order É persistida (I2 fix). Warning documenta."""
    # Evita esperar o backoff real do MLClient (1+2+4=7s) — testes rápidos.
    monkeypatch.setattr("src.ml_client.time.sleep", lambda _: None)
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/orders/search",
        json={
            "results": [
                {
                    "id": 2001,
                    "date_closed": "2026-06-01T10:00:00Z",
                    "status": "paid",
                    "total_amount": 100.0,
                    "payments": [],
                    "shipping": {},
                    "buyer": {"id": 7},
                    "order_items": [
                        {
                            "item": {"id": "MLB222"},
                            "quantity": 1,
                            "unit_price": 100.0,
                        }
                    ],
                }
            ],
            "paging": {"total": 1},
        },
    )
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/orders/search",
        json={"results": [], "paging": {"total": 0}},
    )
    # item falha 4 vezes (MAX_RETRIES=3 -> inicial + 3 retries)
    for _ in range(4):
        responses.add(
            responses.GET,
            "https://api.mercadolibre.com/items/MLB222",
            status=500,
        )
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/post-purchase/v1/claims/search",
        json={"data": []},
    )
    client = MLClient(access_token="tok")
    conn = create_session_db()
    result = ingest_last_6_months(client=client, seller_id=1, conn=conn)
    # I1/I2 fix: order persistida (upsert antes de enrichment), total reflete o DB.
    assert result.total_orders == 1
    db_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert db_count == result.total_orders
    stored_ids = [r[0] for r in conn.execute("SELECT order_id FROM orders").fetchall()]
    assert 2001 in stored_ids
    # Warning documenta a falha de enrichment sem descartar a order.
    assert any("MLB222" in w and "2001" in w for w in result.warnings)
    conn.close()


@responses.activate
def test_ingest_second_item_enrichment_failure_does_not_lose_order(monkeypatch):
    """Order com 2 items, 1 falha em enrichment → order persistida com AMBOS os items."""
    monkeypatch.setattr("src.ml_client.time.sleep", lambda _: None)
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/orders/search",
        json={
            "results": [
                {
                    "id": 3100,
                    "date_closed": "2026-06-10T10:00:00Z",
                    "status": "paid",
                    "total_amount": 200.0,
                    "payments": [],
                    "shipping": {},
                    "buyer": {"id": 22},
                    "order_items": [
                        {"item": {"id": "MLB_OK"}, "quantity": 1, "unit_price": 100.0},
                        {"item": {"id": "MLB_BAD"}, "quantity": 1, "unit_price": 100.0},
                    ],
                }
            ],
            "paging": {"total": 1},
        },
    )
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/orders/search",
        json={"results": [], "paging": {"total": 0}},
    )
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/items/MLB_OK",
        json={"id": "MLB_OK", "title": "Bom", "category_id": "MLB_C1"},
    )
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/categories/MLB_C1",
        json={"id": "MLB_C1", "name": "Cat OK"},
    )
    for _ in range(4):
        responses.add(
            responses.GET,
            "https://api.mercadolibre.com/items/MLB_BAD",
            status=500,
        )
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/post-purchase/v1/claims/search",
        json={"data": []},
    )
    client = MLClient(access_token="tok")
    conn = create_session_db()
    result = ingest_last_6_months(client=client, seller_id=1, conn=conn)
    assert result.total_orders == 1
    # Ambos items na tabela order_items (a order NÃO foi descartada por causa do MLB_BAD).
    stored_items = [r[0] for r in conn.execute("SELECT item_id FROM order_items").fetchall()]
    assert set(stored_items) == {"MLB_OK", "MLB_BAD"}
    # Item OK enriquecido; item BAD só gerou warning.
    cached = [r[0] for r in conn.execute("SELECT item_id FROM items_cache").fetchall()]
    assert cached == ["MLB_OK"]
    assert any("MLB_BAD" in w for w in result.warnings)


@responses.activate
def test_ingest_persist_failure_does_not_count_toward_total():
    """Se _persist_order levanta (payload sem 'status'), total_orders não inclui."""
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/orders/search",
        json={
            "results": [
                {
                    "id": 4001,
                    "date_closed": "2026-06-15T10:00:00Z",
                    # falta "status" — dispara KeyError em _persist_order
                    "total_amount": 50.0,
                    "payments": [],
                    "shipping": {},
                    "buyer": {"id": 44},
                    "order_items": [],
                },
                {
                    "id": 4002,
                    "date_closed": "2026-06-16T10:00:00Z",
                    "status": "paid",
                    "total_amount": 75.0,
                    "payments": [],
                    "shipping": {},
                    "buyer": {"id": 45},
                    "order_items": [],
                },
            ],
            "paging": {"total": 2},
        },
    )
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/orders/search",
        json={"results": [], "paging": {"total": 0}},
    )
    responses.add(
        responses.GET,
        "https://api.mercadolibre.com/post-purchase/v1/claims/search",
        json={"data": []},
    )
    client = MLClient(access_token="tok")
    conn = create_session_db()
    result = ingest_last_6_months(client=client, seller_id=1, conn=conn)
    # 2 recebidas do ML, 1 falha em _persist_order → 1 persistida.
    assert result.total_orders == 1
    db_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    assert db_count == 1
    stored_ids = [r[0] for r in conn.execute("SELECT order_id FROM orders").fetchall()]
    assert stored_ids == [4002]
    assert any("4001" in w for w in result.warnings)


@responses.activate
def test_ingest_reuses_item_cache_across_orders():
    """Regressão: dois pedidos do mesmo item disparam apenas UMA chamada /items/{id}.

    Prova que _ensure_item_cache respeita o cache (early return quando presente)
    — importante pra claim do README sobre custo de API amigável em portfolio.
    """
    same_item_order = {
        "id": None,  # preenchido abaixo
        "date_closed": "2026-06-01T10:00:00Z",
        "status": "paid",
        "total_amount": 50.0,
        "payments": [],
        "shipping": {},
        "buyer": {"id": 100},
        "order_items": [{"item": {"id": "MLB999"}, "quantity": 1, "unit_price": 50.0}],
    }
    order_a = {**same_item_order, "id": 3001, "buyer": {"id": 100}}
    order_b = {**same_item_order, "id": 3002, "buyer": {"id": 101}}
    _mock_ml_endpoints(
        orders_paid=[order_a, order_b],
        items={"MLB999": {"id": "MLB999", "title": "Item Cacheado", "category_id": "MLB2001"}},
        categories={"MLB2001": {"id": "MLB2001", "name": "Categoria Y"}},
    )
    client = MLClient(access_token="tok")
    conn = create_session_db()
    result = ingest_last_6_months(client=client, seller_id=1, conn=conn)
    assert result.total_orders == 2
    assert result.distinct_items == 1
    assert result.distinct_buyers == 2
    # A chave: mock só tem UMA resposta pra /items/MLB999 e UMA pra /categories/MLB2001.
    # Se _ensure_item_cache tivesse chamado duas vezes, responses.calls teria N > 1
    # e o teste falharia com "no more responses registered" ou similar.
    items_calls = [c for c in responses.calls if "/items/MLB999" in c.request.url]
    cat_calls = [c for c in responses.calls if "/categories/MLB2001" in c.request.url]
    assert len(items_calls) == 1, f"Esperava 1 chamada a /items, houve {len(items_calls)}"
    assert len(cat_calls) == 1, f"Esperava 1 chamada a /categories, houve {len(cat_calls)}"
    conn.close()

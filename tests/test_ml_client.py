"""Testes do cliente HTTP do Mercado Livre."""

import pytest
import responses

from src.ml_client import MLAPIError, MLClient, _parse_retry_after

BASE_URL = "https://api.mercadolibre.com"


@pytest.fixture
def client():
    return MLClient(access_token="fake-token")


@responses.activate
def test_get_returns_json_on_success(client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/users/me",
        json={"id": 123, "nickname": "TESTE"},
        status=200,
    )
    result = client.get("/users/me")
    assert result["id"] == 123


@responses.activate
def test_get_retries_on_5xx_then_succeeds(client):
    responses.add(responses.GET, f"{BASE_URL}/users/me", status=500)
    responses.add(responses.GET, f"{BASE_URL}/users/me", status=500)
    responses.add(responses.GET, f"{BASE_URL}/users/me", json={"id": 7}, status=200)
    result = client.get("/users/me")
    assert result["id"] == 7
    assert len(responses.calls) == 3


@responses.activate
def test_get_raises_after_max_retries(client):
    for _ in range(4):
        responses.add(responses.GET, f"{BASE_URL}/users/me", status=503)
    with pytest.raises(MLAPIError):
        client.get("/users/me")


@responses.activate
def test_get_respects_retry_after_on_429(client):
    responses.add(responses.GET, f"{BASE_URL}/users/me", status=429, headers={"Retry-After": "0"})
    responses.add(responses.GET, f"{BASE_URL}/users/me", json={"id": 1}, status=200)
    result = client.get("/users/me")
    assert result["id"] == 1


@responses.activate
def test_get_raises_after_max_retries_on_429(client):
    """429 respeita MAX_RETRIES (não fica em loop infinito)."""
    for _ in range(4):
        responses.add(
            responses.GET, f"{BASE_URL}/users/me", status=429, headers={"Retry-After": "0"}
        )
    with pytest.raises(MLAPIError) as exc:
        client.get("/users/me")
    assert exc.value.status_code == 429


def test_parse_retry_after_handles_seconds():
    assert _parse_retry_after("5", default=1.0) == 5.0


def test_parse_retry_after_handles_http_date():
    """Formato HTTP-date da RFC 7231 não deve levantar ValueError."""
    result = _parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT", default=1.0)
    # Data passada → delta negativo é clampeado em 0.
    assert result == 0.0


def test_parse_retry_after_fallback_on_garbage():
    assert _parse_retry_after("garbage-not-a-date", default=2.5) == 2.5


def test_parse_retry_after_uses_default_when_missing():
    assert _parse_retry_after(None, default=7.0) == 7.0


@responses.activate
def test_get_raises_on_401(client):
    responses.add(responses.GET, f"{BASE_URL}/users/me", status=401)
    with pytest.raises(MLAPIError) as exc:
        client.get("/users/me")
    assert exc.value.status_code == 401


@responses.activate
def test_get_orders_single_page(client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/orders/search",
        json={
            "paging": {"total": 2, "offset": 0, "limit": 50},
            "results": [
                {"id": 1, "total_amount": 100.0},
                {"id": 2, "total_amount": 200.0},
            ],
        },
        status=200,
    )
    orders = client.get_orders(
        seller_id=999,
        status="paid",
        date_from="2026-06-08T00:00:00",
        date_to="2026-06-15T00:00:00",
    )
    assert [o["id"] for o in orders] == [1, 2]


@responses.activate
def test_get_orders_multiple_pages(client):
    # Página 1
    responses.add(
        responses.GET,
        f"{BASE_URL}/orders/search",
        json={"paging": {"total": 3, "offset": 0, "limit": 2}, "results": [{"id": 1}, {"id": 2}]},
        status=200,
    )
    # Página 2
    responses.add(
        responses.GET,
        f"{BASE_URL}/orders/search",
        json={"paging": {"total": 3, "offset": 2, "limit": 2}, "results": [{"id": 3}]},
        status=200,
    )
    orders = client.get_orders(
        seller_id=999,
        status="paid",
        date_from="2026-06-08T00:00:00",
        date_to="2026-06-15T00:00:00",
        page_size=2,
    )
    assert [o["id"] for o in orders] == [1, 2, 3]


@responses.activate
def test_get_item(client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/items/MLB123",
        json={"id": "MLB123", "title": "Lanterna CG 150", "category_id": "MLB-cat-lights"},
        status=200,
    )
    item = client.get_item("MLB123")
    assert item["title"] == "Lanterna CG 150"


@responses.activate
def test_get_category(client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/categories/MLB-cat-1",
        json={"id": "MLB-cat-1", "name": "Iluminação"},
        status=200,
    )
    assert client.get_category("MLB-cat-1")["name"] == "Iluminação"


@responses.activate
def test_get_user(client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/users/999",
        json={
            "id": 999,
            "seller_reputation": {"level_id": "5_green", "metrics": {"claims": {"value": 0}}},
        },
        status=200,
    )
    user = client.get_user(999)
    assert user["seller_reputation"]["level_id"] == "5_green"


@responses.activate
def test_get_claims(client):
    responses.add(
        responses.GET,
        f"{BASE_URL}/post-purchase/v1/claims/search",
        json={"data": [{"id": 1, "status": "opened"}], "paging": {"total": 1}},
        status=200,
    )
    claims = client.get_claims(seller_id=999, date_from="2026-06-01T00:00:00")
    assert len(claims) == 1
    assert claims[0]["status"] == "opened"


@responses.activate
def test_get_claims_filters_by_date_to(client):
    """date_to opcional: filtra client-side quando informado."""
    responses.add(
        responses.GET,
        f"{BASE_URL}/post-purchase/v1/claims/search",
        json={
            "data": [
                {"id": 1, "date_created": "2026-06-05T10:00:00"},
                {"id": 2, "date_created": "2026-06-20T10:00:00"},
            ],
            "paging": {"total": 2},
        },
        status=200,
    )
    claims = client.get_claims(
        seller_id=999,
        date_from="2026-06-01T00:00:00",
        date_to="2026-06-15T00:00:00",
    )
    assert [c["id"] for c in claims] == [1]

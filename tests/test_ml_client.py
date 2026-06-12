"""Testes do cliente HTTP do Mercado Livre."""
import pytest
import responses

from src.ml_client import MLClient, MLAPIError

BASE_URL = "https://api.mercadolibre.com"


@pytest.fixture
def client():
    return MLClient(access_token="fake-token")


@responses.activate
def test_get_returns_json_on_success(client):
    responses.add(
        responses.GET, f"{BASE_URL}/users/me",
        json={"id": 123, "nickname": "TESTE"}, status=200,
    )
    result = client.get("/users/me")
    assert result["id"] == 123


@responses.activate
def test_get_retries_on_5xx_then_succeeds(client):
    responses.add(responses.GET, f"{BASE_URL}/users/me", status=500)
    responses.add(responses.GET, f"{BASE_URL}/users/me", status=500)
    responses.add(responses.GET, f"{BASE_URL}/users/me",
                  json={"id": 7}, status=200)
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
    responses.add(responses.GET, f"{BASE_URL}/users/me",
                  status=429, headers={"Retry-After": "0"})
    responses.add(responses.GET, f"{BASE_URL}/users/me",
                  json={"id": 1}, status=200)
    result = client.get("/users/me")
    assert result["id"] == 1


@responses.activate
def test_get_raises_on_401(client):
    responses.add(responses.GET, f"{BASE_URL}/users/me", status=401)
    with pytest.raises(MLAPIError) as exc:
        client.get("/users/me")
    assert exc.value.status_code == 401


@responses.activate
def test_get_orders_single_page(client):
    responses.add(
        responses.GET, f"{BASE_URL}/orders/search",
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
        seller_id=999, status="paid",
        date_from="2026-06-08T00:00:00", date_to="2026-06-15T00:00:00",
    )
    assert [o["id"] for o in orders] == [1, 2]


@responses.activate
def test_get_orders_multiple_pages(client):
    # Página 1
    responses.add(
        responses.GET, f"{BASE_URL}/orders/search",
        json={"paging": {"total": 3, "offset": 0, "limit": 2},
              "results": [{"id": 1}, {"id": 2}]},
        status=200,
    )
    # Página 2
    responses.add(
        responses.GET, f"{BASE_URL}/orders/search",
        json={"paging": {"total": 3, "offset": 2, "limit": 2},
              "results": [{"id": 3}]},
        status=200,
    )
    orders = client.get_orders(
        seller_id=999, status="paid",
        date_from="2026-06-08T00:00:00", date_to="2026-06-15T00:00:00",
        page_size=2,
    )
    assert [o["id"] for o in orders] == [1, 2, 3]

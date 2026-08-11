"""Teste de integração do orquestrador de ingestão."""

from datetime import UTC, datetime, timedelta

import responses

from src.auth import TokenSet, TokenStore
from src.main import ingest_window
from src.storage import connect, get_orders_in_range

BASE_URL = "https://api.mercadolibre.com"


@responses.activate
def test_ingest_window_persists_orders_items_claims_and_logs_run(tmp_path, monkeypatch):
    # 1) Setup ambiente
    tokens_path = tmp_path / "tokens.json"
    db_path = tmp_path / "historico.db"
    store = TokenStore(tokens_path)
    store.save(
        TokenSet(
            access_token="acc-1",
            refresh_token="ref-1",
            expires_at=datetime.now(UTC) + timedelta(hours=5),
        )
    )
    monkeypatch.setenv("ML_CLIENT_ID", "cid")
    monkeypatch.setenv("ML_CLIENT_SECRET", "csec")
    monkeypatch.setenv("ML_USER_ID", "999")

    # 2) Mocks ML
    responses.add(
        responses.GET,
        f"{BASE_URL}/orders/search",
        json={
            "paging": {"total": 1, "offset": 0, "limit": 50},
            "results": [
                {
                    "id": 1001,
                    "date_closed": "2026-06-10T14:30:00.000-03:00",
                    "status": "paid",
                    "total_amount": 250.0,
                    "payments": [{"marketplace_fee": 30.0}],
                    "shipping": {"list_cost": 15.0},
                    "buyer": {"id": 8888},
                    "order_items": [{"item": {"id": "MLB1"}, "quantity": 1, "unit_price": 250.0}],
                }
            ],
        },
        status=200,
    )
    # Segunda chamada (status=cancelled) → vazio
    responses.add(
        responses.GET,
        f"{BASE_URL}/orders/search",
        json={"paging": {"total": 0, "offset": 0, "limit": 50}, "results": []},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/items/MLB1",
        json={"id": "MLB1", "title": "Lanterna CG 150", "category_id": "MLB-cat-A"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/categories/MLB-cat-A",
        json={"id": "MLB-cat-A", "name": "Iluminação"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/post-purchase/v1/claims/search",
        json={"data": [], "paging": {"total": 0}},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/users/999",
        json={
            "id": 999,
            "seller_reputation": {"level_id": "5_green", "metrics": {"claims": {"value": 0}}},
        },
        status=200,
    )

    # 3) Executar
    result = ingest_window(
        tokens_path=tokens_path,
        db_path=db_path,
        date_from="2026-06-08T00:00:00.000-03:00",
        date_to="2026-06-15T00:00:00.000-03:00",
    )

    # 4) Validar
    conn = connect(db_path)
    orders = get_orders_in_range(conn, "2026-06-08", "2026-06-15")
    assert len(orders) == 1
    assert orders[0]["order_id"] == 1001

    items = conn.execute("SELECT * FROM items_cache").fetchall()
    assert items[0]["title"] == "Lanterna CG 150"

    cat = conn.execute("SELECT * FROM categories_cache").fetchall()
    assert cat[0]["name"] == "Iluminação"

    last_run = conn.execute("SELECT * FROM runs").fetchone()
    assert last_run["status"] == "ok"
    assert result["orders_fetched"] == 1

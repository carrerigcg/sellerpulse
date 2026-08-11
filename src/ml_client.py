"""Cliente HTTP para a API do Mercado Livre."""

from __future__ import annotations

import time
from typing import Any

import requests

BASE_URL = "https://api.mercadolibre.com"
MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # segundos


class MLAPIError(Exception):
    """Erro vindo da API do Mercado Livre."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"ML API {status_code}: {message}")
        self.status_code = status_code


class MLClient:
    """Cliente HTTP fino — sabe paginar, fazer retry, parsear JSON."""

    def __init__(self, access_token: str, base_url: str = BASE_URL) -> None:
        self._access_token = access_token
        self._base_url = base_url
        self._session = requests.Session()

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET um endpoint do ML, com retry em 5xx e 429."""
        url = f"{self._base_url}{path}"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        last_response = None
        for attempt in range(MAX_RETRIES + 1):
            response = self._session.get(url, headers=headers, params=params, timeout=30)
            if response.status_code < 400:
                return response.json()
            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", BACKOFF_BASE))
                time.sleep(retry_after)
                continue
            if 500 <= response.status_code < 600 and attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE * (2**attempt))
                continue
            last_response = response
            break
        # Se chegou aqui, ou esgotou retries ou foi 4xx não-recuperável
        if last_response is None:
            last_response = response
        raise MLAPIError(last_response.status_code, last_response.text[:200])

    def get_orders(
        self,
        *,
        seller_id: int,
        status: str | None,
        date_from: str,
        date_to: str,
        page_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Busca pedidos com paginação automática.

        Args:
            seller_id: ID do vendedor (USER_ID).
            status: 'paid', 'cancelled', ou None para todos.
            date_from: ISO8601, inclusive.
            date_to: ISO8601, exclusive.
            page_size: pedidos por página (max 50).
        """
        params_base: dict[str, Any] = {
            "seller": seller_id,
            "order.date_created.from": date_from,
            "order.date_created.to": date_to,
            "sort": "date_desc",
            "limit": page_size,
        }
        if status is not None:
            params_base["order.status"] = status

        all_orders: list[dict[str, Any]] = []
        offset = 0
        while True:
            params = {**params_base, "offset": offset}
            data = self.get("/orders/search", params=params)
            results = data.get("results", [])
            all_orders.extend(results)
            paging = data.get("paging", {})
            total = paging.get("total", 0)
            if offset + page_size >= total or not results:
                break
            offset += page_size
        return all_orders

    def get_item(self, item_id: str) -> dict[str, Any]:
        """Detalhe de um item (title + category_id)."""
        return self.get(f"/items/{item_id}")

    def get_category(self, category_id: str) -> dict[str, Any]:
        """Detalhe de uma categoria ML (nome em português)."""
        return self.get(f"/categories/{category_id}")

    def get_user(self, user_id: int) -> dict[str, Any]:
        """Dados do usuário, incluindo seller_reputation."""
        return self.get(f"/users/{user_id}")

    def get_claims(self, *, seller_id: int, date_from: str) -> list[dict[str, Any]]:
        """Reclamações/claims pós-compra do vendedor a partir de date_from."""
        params = {
            "seller_id": seller_id,
            "date_created.from": date_from,
        }
        data = self.get("/post-purchase/v1/claims/search", params=params)
        return data.get("data", [])

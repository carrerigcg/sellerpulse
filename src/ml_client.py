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
                time.sleep(BACKOFF_BASE * (2 ** attempt))
                continue
            last_response = response
            break
        # Se chegou aqui, ou esgotou retries ou foi 4xx não-recuperável
        if last_response is None:
            last_response = response
        raise MLAPIError(last_response.status_code, last_response.text[:200])

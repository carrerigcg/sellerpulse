from fastapi.testclient import TestClient

from backend.main import app

from .conftest import TEST_DATABASE_URL


def test_health_check(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

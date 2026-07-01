"""Tests du endpoint GET /health."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_retourne_200() -> None:
    """GET /health doit retourner 200 avec {"status": "ok"}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

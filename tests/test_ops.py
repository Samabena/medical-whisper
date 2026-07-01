"""Tests de robustesse : erreurs uniformes (OPS-1) et auth (OPS-3)."""

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_API_KEY

client = TestClient(app)
HEADERS = {"X-API-Key": TEST_API_KEY}

# ── OPS-1 : codes d'erreur homogènes ─────────────────────────────────────────


def test_health_public_sans_cle() -> None:
    """/health doit être accessible sans clé API."""
    response = client.get("/health")
    assert response.status_code == 200


def test_404_contient_erreur_et_detail() -> None:
    """Un 404 doit retourner {erreur, detail}."""
    response = client.get("/v1/forms/form_inconnu", headers=HEADERS)
    assert response.status_code == 404
    data = response.json()
    assert "erreur" in data
    assert "detail" in data


# ── OPS-3 : authentification par X-API-Key ────────────────────────────────────


def test_appel_sans_cle_retourne_401() -> None:
    """Un appel /v1/* sans X-API-Key doit retourner 401."""
    response = client.get("/v1/forms")
    assert response.status_code == 401
    data = response.json()
    assert "erreur" in data


def test_appel_cle_invalide_retourne_401() -> None:
    """Un appel avec une mauvaise clé doit retourner 401."""
    response = client.get("/v1/forms", headers={"X-API-Key": "mauvaise-cle"})
    assert response.status_code == 401


def test_appel_cle_valide_retourne_200() -> None:
    """Un appel avec la bonne clé doit passer."""
    response = client.get("/v1/forms", headers=HEADERS)
    assert response.status_code == 200

"""Tests des endpoints de découverte des formulaires (FORM-3)."""

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_API_KEY

client = TestClient(app)
HEADERS = {"X-API-Key": TEST_API_KEY}


def test_lister_formulaires_retourne_200() -> None:
    """GET /v1/forms doit retourner 200 avec la liste des form_id."""
    response = client.get("/v1/forms", headers=HEADERS)
    assert response.status_code == 200
    ids = response.json()
    assert isinstance(ids, list)
    assert "consultation_v1" in ids
    assert "rapport_chirurgie_v1" in ids
    assert "dossier_medical_v1" in ids


def test_obtenir_schema_consultation() -> None:
    """GET /v1/forms/consultation_v1 doit retourner le JSON Schema."""
    response = client.get("/v1/forms/consultation_v1", headers=HEADERS)
    assert response.status_code == 200
    schema = response.json()
    assert schema.get("title") or schema.get("$defs") or "properties" in schema


def test_obtenir_schema_rapport_chirurgie() -> None:
    """GET /v1/forms/rapport_chirurgie_v1 doit retourner le JSON Schema."""
    response = client.get("/v1/forms/rapport_chirurgie_v1", headers=HEADERS)
    assert response.status_code == 200
    assert "properties" in response.json()


def test_obtenir_schema_inconnu_retourne_404() -> None:
    """GET /v1/forms/formulaire_inexistant doit retourner 404."""
    response = client.get("/v1/forms/formulaire_inexistant", headers=HEADERS)
    assert response.status_code == 404
    assert "detail" in response.json()

"""FORM-4.1 — API admin du constructeur de formulaires (CRUD, versionnage, publication)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.interface import deps
from app.interface.main import create_app
from tests.fakes import InMemoryFormRepo


def _client() -> TestClient:
    forms = InMemoryFormRepo()
    app = create_app()
    app.dependency_overrides[deps.form_repo] = lambda: forms
    app.dependency_overrides[deps.require_admin] = lambda: "admin@local"
    return TestClient(app)


_CONSULT = {
    "form_id": "consult",
    "titre": "Consultation",
    "langue": "fr",
    "fields": [
        {"name": "nom", "label": "Nom", "type": "string", "required": True},
        {"name": "sexe", "label": "Sexe", "type": "enum", "enum_values": ["m", "f"]},
    ],
}


def test_creation_draft_v1():
    client = _client()
    r = client.post("/admin/api/accounts/1/forms", json=_CONSULT)
    assert r.status_code == 201
    body = r.json()
    assert body["version"] == 1 and body["statut"] == "draft"
    assert body["fields"][0]["name"] == "nom"


def test_doublon_form_id_409():
    client = _client()
    client.post("/admin/api/accounts/1/forms", json=_CONSULT)
    assert client.post("/admin/api/accounts/1/forms", json=_CONSULT).status_code == 409


def test_enum_sans_valeurs_422():
    client = _client()
    invalide = {
        "form_id": "f",
        "titre": "F",
        "fields": [{"name": "sexe", "label": "Sexe", "type": "enum"}],  # pas de enum_values
    }
    assert client.post("/admin/api/accounts/1/forms", json=invalide).status_code == 422


def test_edition_draft_en_place_puis_publication_puis_nouvelle_version():
    client = _client()
    client.post("/admin/api/accounts/1/forms", json=_CONSULT)

    # Édition du draft → reste v1.
    r = client.patch("/admin/api/accounts/1/forms/consult", json={"titre": "Consultation v1b"})
    assert r.json()["version"] == 1 and r.json()["titre"] == "Consultation v1b"

    # Publication → published.
    pub = client.post("/admin/api/accounts/1/forms/consult/publish")
    assert pub.json()["statut"] == "published" and pub.json()["version"] == 1

    # Édition d'un formulaire publié → nouvelle version draft v2 (la v1 publiée reste).
    r2 = client.patch("/admin/api/accounts/1/forms/consult", json={"titre": "Consultation v2"})
    assert r2.json()["version"] == 2 and r2.json()["statut"] == "draft"

    # get renvoie la dernière version ; list contient les deux.
    assert client.get("/admin/api/accounts/1/forms/consult").json()["version"] == 2
    assert len(client.get("/admin/api/accounts/1/forms").json()) == 2


def test_formulaires_proteges():
    client = TestClient(create_app())
    assert client.post("/admin/api/accounts/1/forms", json=_CONSULT).status_code == 401

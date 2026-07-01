"""FORM-4.3 — découverte client : seules les versions publiées sont visibles, scopées au compte."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.domain.entities import Account, FormDefinition, FormField
from app.domain.value_objects import FieldType, FormStatus, Language
from app.interface import deps
from app.interface.main import create_app
from tests.fakes import InMemoryFormRepo


def _client() -> TestClient:
    forms = InMemoryFormRepo()
    account = Account(nom="App", email_contact="a@ex.com", langue=Language.FR, id=1)

    async def seed():
        await forms.add(
            FormDefinition(
                account_id=1, form_id="consult", titre="Consultation",
                statut=FormStatus.PUBLISHED,
                fields=[FormField("nom", "Nom", FieldType.STRING, required=True)],
            )
        )
        # Brouillon non publié → invisible au client.
        await forms.add(FormDefinition(account_id=1, form_id="brouillon", titre="WIP"))

    asyncio.run(seed())

    app = create_app()
    app.dependency_overrides[deps.form_repo] = lambda: forms
    app.dependency_overrides[deps.current_account] = lambda: account
    return TestClient(app)


def test_liste_seulement_les_publies():
    client = _client()
    items = client.get("/v1/integration/forms").json()
    ids = {f["form_id"] for f in items}
    assert ids == {"consult"}  # le brouillon n'apparaît pas


def test_schema_formulaire_publie():
    client = _client()
    r = client.get("/v1/integration/forms/consult")
    assert r.status_code == 200
    assert r.json()["fields"][0]["name"] == "nom"


def test_formulaire_non_publie_404():
    client = _client()
    assert client.get("/v1/integration/forms/brouillon").status_code == 404

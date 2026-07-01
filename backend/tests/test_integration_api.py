"""INT-5.1 / INT-5.2 — routeur d'intégration de bout en bout (auth, session, résultat)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.domain.entities import Account, ApiKey, FormDefinition, FormField
from app.domain.value_objects import FieldType, Language
from app.infrastructure.results.memory_store import InMemorySessionResultStore
from app.infrastructure.security.api_keys import generer_cle
from app.interface import deps
from app.interface.main import create_app
from tests.fakes import (
    InMemoryAccountRepo,
    InMemoryApiKeyRepo,
    InMemoryFormRepo,
    InMemorySessionRepo,
    InMemoryUsageRepo,
)


def _seed() -> SimpleNamespace:
    accounts, keys = InMemoryAccountRepo(), InMemoryApiKeyRepo()
    forms, sessions = InMemoryFormRepo(), InMemorySessionRepo()
    results, usage = InMemorySessionResultStore(), InMemoryUsageRepo()

    async def go():
        account = await accounts.add(
            Account(nom="App", email_contact="app@ex.com", langue=Language.EN)
        )
        cle = generer_cle()
        await keys.add(
            ApiKey(account_id=account.id, key_prefix=cle.key_prefix, key_hash=cle.key_hash)
        )
        await forms.add(
            FormDefinition(
                account_id=account.id,
                form_id="consult",
                titre="Consult",
                fields=[FormField("nom", "Nom", FieldType.STRING, required=True)],
            )
        )
        return account, cle.cle_claire

    account, cle_claire = asyncio.run(go())
    return SimpleNamespace(
        accounts=accounts, keys=keys, forms=forms, sessions=sessions,
        results=results, usage=usage, account=account, cle=cle_claire,
    )


def _client(s: SimpleNamespace) -> TestClient:
    app = create_app()
    app.dependency_overrides[deps.account_repo] = lambda: s.accounts
    app.dependency_overrides[deps.apikey_repo] = lambda: s.keys
    app.dependency_overrides[deps.form_repo] = lambda: s.forms
    app.dependency_overrides[deps.session_repo] = lambda: s.sessions
    app.dependency_overrides[deps.result_store] = lambda: s.results
    app.dependency_overrides[deps.usage_repo] = lambda: s.usage
    return TestClient(app)


def test_session_requiert_cle_api():
    client = _client(_seed())
    assert client.post("/v1/integration/sessions", json={"form_id": "consult"}).status_code == 401


def test_session_cle_invalide():
    client = _client(_seed())
    r = client.post(
        "/v1/integration/sessions",
        json={"form_id": "consult"},
        headers={"X-API-Key": "mauvaise"},
    )
    assert r.status_code == 401


def test_creation_session_puis_resultat():
    s = _seed()
    client = _client(s)
    auth = {"X-API-Key": s.cle}

    r = client.post("/v1/integration/sessions", json={"form_id": "consult"}, headers=auth)
    assert r.status_code == 201
    data = r.json()
    assert data["language"] == "en"  # langue du compte (pas de surcharge formulaire)
    assert data["ws_url"].endswith(f"/v1/live/{data['session_id']}")
    assert data["token"]
    assert data["form_schema"]["fields"][0]["name"] == "nom"

    # Usage enregistré (métadonnée de facturation).
    assert asyncio.run(s.usage.count_by_endpoint(s.account.id)) == {"session_create": 1}

    sid = data["session_id"]
    # Résultat pas encore disponible.
    assert client.get(f"/v1/integration/sessions/{sid}/result", headers=auth).status_code == 404
    # On dépose le résultat (simule la clôture EPIC 8) puis on le récupère.
    asyncio.run(s.results.save(sid, {"statut": "termine", "formulaire": {"nom": "Martin"}}))
    r2 = client.get(f"/v1/integration/sessions/{sid}/result", headers=auth)
    assert r2.status_code == 200 and r2.json()["formulaire"]["nom"] == "Martin"


def test_formulaire_inconnu_404():
    s = _seed()
    client = _client(s)
    r = client.post(
        "/v1/integration/sessions", json={"form_id": "absent"}, headers={"X-API-Key": s.cle}
    )
    assert r.status_code == 404

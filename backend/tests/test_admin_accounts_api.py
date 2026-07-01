"""ADM-3.1 / 3.2 / 3.3 — API admin comptes, langue, persona, clés API."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.application.integration.authenticate import authenticate_api_key
from app.domain.errors import UnauthorizedError
from app.infrastructure.security.hashing import Sha256KeyHasher
from app.interface import deps
from app.interface.main import create_app
from tests.fakes import InMemoryAccountRepo, InMemoryApiKeyRepo


def _client() -> tuple[TestClient, SimpleNamespace]:
    accounts, keys, hasher = InMemoryAccountRepo(), InMemoryApiKeyRepo(), Sha256KeyHasher()
    app = create_app()
    app.dependency_overrides[deps.account_repo] = lambda: accounts
    app.dependency_overrides[deps.apikey_repo] = lambda: keys
    app.dependency_overrides[deps.key_hasher] = lambda: hasher
    app.dependency_overrides[deps.require_admin] = lambda: "admin@local"
    return TestClient(app), SimpleNamespace(accounts=accounts, keys=keys, hasher=hasher)


def test_crud_compte_langue_et_persona():
    client, _ = _client()
    r = client.post(
        "/admin/api/accounts",
        json={"nom": "App EN", "email_contact": "en@ex.com", "langue": "en"},
    )
    assert r.status_code == 201 and r.json()["langue"] == "en"
    aid = r.json()["id"]

    # Email en doublon → 409.
    assert (
        client.post("/admin/api/accounts", json={"nom": "x", "email_contact": "en@ex.com"}).status_code
        == 409
    )

    assert any(a["id"] == aid for a in client.get("/admin/api/accounts").json())

    # Changer la langue + persona/voix (ADM-3.1 + ADM-3.3).
    r2 = client.patch(
        f"/admin/api/accounts/{aid}",
        json={"langue": "fr", "persona_prompt": "Assistant clinique", "voice_prompt": "voix-fr"},
    )
    assert r2.status_code == 200
    assert r2.json()["langue"] == "fr"
    assert r2.json()["persona_prompt"] == "Assistant clinique"

    # Désactivation via patch.
    assert client.patch(f"/admin/api/accounts/{aid}", json={"actif": False}).json()["actif"] is False


def test_cles_rotation_revocation_et_authentification():
    client, s = _client()
    aid = client.post("/admin/api/accounts", json={"nom": "A", "email_contact": "a@ex.com"}).json()["id"]

    k1 = client.post(f"/admin/api/accounts/{aid}/keys", json={"label": "k1"}).json()
    k2 = client.post(f"/admin/api/accounts/{aid}/keys", json={"label": "k2"}).json()
    assert k1["cle_en_clair"] and k2["cle_en_clair"] and k1["cle_en_clair"] != k2["cle_en_clair"]

    # Listing masqué : jamais la clé en clair.
    listing = client.get(f"/admin/api/accounts/{aid}/keys").json()
    assert len(listing) == 2
    assert all("cle_en_clair" not in k for k in listing)
    assert all(k["key_masquee"].endswith("…") for k in listing)

    # La clé générée authentifie réellement un appel /v1 (cross-check ADM-3.2).
    acc = asyncio.run(authenticate_api_key(k1["cle_en_clair"], s.accounts, s.keys, s.hasher))
    assert acc.id == aid

    # Révocation immédiate de k1.
    r = client.delete(f"/admin/api/accounts/{aid}/keys/{k1['id']}")
    assert r.status_code == 200 and r.json()["actif"] is False
    with pytest.raises(UnauthorizedError):
        asyncio.run(authenticate_api_key(k1["cle_en_clair"], s.accounts, s.keys, s.hasher))
    # k2 reste valide (rotation sans coupure).
    assert asyncio.run(authenticate_api_key(k2["cle_en_clair"], s.accounts, s.keys, s.hasher)).id == aid


def test_revocation_scopee_au_compte():
    client, _ = _client()
    a = client.post("/admin/api/accounts", json={"nom": "A", "email_contact": "a@ex.com"}).json()["id"]
    b = client.post("/admin/api/accounts", json={"nom": "B", "email_contact": "b@ex.com"}).json()["id"]
    ka = client.post(f"/admin/api/accounts/{a}/keys").json()
    # Révoquer la clé de A via le chemin de B → 404 (isolation).
    assert client.delete(f"/admin/api/accounts/{b}/keys/{ka['id']}").status_code == 404


def test_routes_admin_protegees():
    client = TestClient(create_app())  # aucune override → require_admin actif
    assert client.get("/admin/api/accounts").status_code == 401

"""Tests du portail admin web (EPIC 7) — auth cookie + actions UI."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_ADMIN_PASSWORD


def _client_connecte() -> TestClient:
    """Retourne un TestClient authentifié (cookie de session admin)."""
    client = TestClient(app)
    r = client.post(
        "/admin/connexion",
        data={"mot_de_passe": TEST_ADMIN_PASSWORD},
        follow_redirects=False,
    )
    assert r.status_code == 302
    return client


# ── Authentification ──────────────────────────────────────────────────────────


def test_login_mauvais_mot_de_passe() -> None:
    client = TestClient(app)
    r = client.post(
        "/admin/connexion", data={"mot_de_passe": "faux"}, follow_redirects=False
    )
    assert r.status_code == 401


def test_login_correct_redirige_dashboard() -> None:
    client = TestClient(app)
    r = client.post(
        "/admin/connexion",
        data={"mot_de_passe": TEST_ADMIN_PASSWORD},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/admin/"


def test_dashboard_non_connecte_redirige_login() -> None:
    client = TestClient(app)
    r = client.get("/admin/", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/admin/connexion"


# ── Actions UI protégées par cookie (régression bugs templates) ───────────────


def test_creer_compte_via_formulaire() -> None:
    """POST /admin/comptes (form HTML) doit créer le compte et rediriger vers le dashboard."""
    client = _client_connecte()
    r = client.post(
        "/admin/comptes",
        data={"nom": "ACME", "email_contact": "contact@acme.io"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/admin/"
    # Le compte apparaît dans le tableau de bord
    assert "ACME" in client.get("/admin/").text


def test_generer_puis_revoquer_cle() -> None:
    """Génération de clé puis révocation via les routes UI (cookie, pas X-Admin-Key)."""
    client = _client_connecte()
    client.post(
        "/admin/comptes",
        data={"nom": "ACME", "email_contact": "contact@acme.io"},
        follow_redirects=False,
    )
    # Génère une clé pour le compte 1
    r = client.post("/admin/comptes/1/cles", follow_redirects=False)
    assert r.status_code == 200
    # Révoque la clé 1
    r = client.post("/admin/comptes/1/cles/1/revoquer", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/admin/comptes/1/cles"


def test_creer_compte_non_connecte_redirige() -> None:
    """Sans session, l'action de création doit rediriger vers le login (pas de création)."""
    client = TestClient(app)
    r = client.post(
        "/admin/comptes",
        data={"nom": "Pirate", "email_contact": "x@x.io"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "/admin/connexion"

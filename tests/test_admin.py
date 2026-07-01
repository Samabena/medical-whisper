"""Tests ADMIN-1/2/3/4 : comptes, clés, usage, portail web."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_ADMIN_PASSWORD, TEST_API_KEY

ADMIN_HEADERS = {"X-Admin-Key": TEST_ADMIN_PASSWORD}
V1_HEADERS = {"X-API-Key": TEST_API_KEY}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _creer_compte(client: TestClient, nom: str = "Acme", email: str = "acme@test.com") -> dict:
    r = client.post(
        "/admin/api/comptes",
        json={"nom": nom, "email_contact": email},
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _creer_cle(client: TestClient, compte_id: str) -> dict:
    r = client.post(f"/admin/api/comptes/{compte_id}/cles", headers=ADMIN_HEADERS)
    assert r.status_code == 201, r.text
    return r.json()


# ── ADMIN-1 : modèle de compte + persistance ─────────────────────────────────


def test_creer_compte() -> None:
    client = TestClient(app)
    data = _creer_compte(client)
    assert data["nom"] == "Acme"
    assert data["email_contact"] == "acme@test.com"
    assert data["actif"] is True
    assert "id" in data
    assert "date_creation" in data


def test_lister_comptes_vide() -> None:
    client = TestClient(app)
    r = client.get("/admin/api/comptes", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json() == []


def test_lister_comptes_apres_creation() -> None:
    client = TestClient(app)
    _creer_compte(client, "A", "a@test.com")
    _creer_compte(client, "B", "b@test.com")
    r = client.get("/admin/api/comptes", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_compte_inconnu() -> None:
    client = TestClient(app)
    r = client.get("/admin/api/comptes/id-inconnu", headers=ADMIN_HEADERS)
    assert r.status_code == 404


def test_desactiver_compte() -> None:
    client = TestClient(app)
    compte = _creer_compte(client)
    cle_data = _creer_cle(client, compte["id"])
    cle_valide = cle_data["cle_en_clair"]

    # La clé fonctionne avant désactivation
    assert client.get("/v1/forms", headers={"X-API-Key": cle_valide}).status_code == 200

    # Désactivation du compte
    r = client.patch(f"/admin/api/comptes/{compte['id']}/desactiver", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["actif"] is False

    # La clé est refusée après désactivation
    assert client.get("/v1/forms", headers={"X-API-Key": cle_valide}).status_code == 401


def test_cle_hachee_valide_lauth() -> None:
    """Une clé DB (hachée) valide bien l'auth /v1."""
    client = TestClient(app)
    compte = _creer_compte(client)
    cle_data = _creer_cle(client, compte["id"])
    cle = cle_data["cle_en_clair"]

    r = client.get("/v1/forms", headers={"X-API-Key": cle})
    assert r.status_code == 200


def test_cle_config_toujours_valide() -> None:
    """La clé de config (TEST_API_KEY) continue de fonctionner (backward compat)."""
    client = TestClient(app)
    r = client.get("/v1/forms", headers=V1_HEADERS)
    assert r.status_code == 200


# ── ADMIN-2 : création / rotation / révocation ───────────────────────────────


def test_creer_cle_affiche_en_clair_une_seule_fois() -> None:
    client = TestClient(app)
    compte = _creer_compte(client)
    cle_data = _creer_cle(client, compte["id"])
    assert "cle_en_clair" in cle_data
    assert len(cle_data["cle_en_clair"]) > 20
    # La liste masque la clé
    r = client.get(f"/admin/api/comptes/{compte['id']}/cles", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    for k in r.json():
        assert "cle_en_clair" not in k
        assert "..." in k["cle_masquee"]


def test_rotation_deux_cles_actives_en_parallele() -> None:
    """Deux clés actives simultanément permettent la rotation sans coupure."""
    client = TestClient(app)
    compte = _creer_compte(client)
    k1 = _creer_cle(client, compte["id"])["cle_en_clair"]
    k2 = _creer_cle(client, compte["id"])["cle_en_clair"]

    # Les deux clés fonctionnent
    assert client.get("/v1/forms", headers={"X-API-Key": k1}).status_code == 200
    assert client.get("/v1/forms", headers={"X-API-Key": k2}).status_code == 200

    # Vérifier que les deux apparaissent dans la liste
    r = client.get(f"/admin/api/comptes/{compte['id']}/cles", headers=ADMIN_HEADERS)
    assert len([k for k in r.json() if k["actif"]]) == 2


def test_revocation_immediate() -> None:
    """Une clé révoquée est refusée immédiatement."""
    client = TestClient(app)
    compte = _creer_compte(client)
    k1 = _creer_cle(client, compte["id"])
    k2 = _creer_cle(client, compte["id"])

    cle_valide = k1["cle_en_clair"]
    cle_id_a_revoquer = k1["id"]

    # Révocation de k1
    r = client.delete(
        f"/admin/api/comptes/{compte['id']}/cles/{cle_id_a_revoquer}",
        headers=ADMIN_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["actif"] is False

    # k1 refusée, k2 toujours valide
    assert client.get("/v1/forms", headers={"X-API-Key": cle_valide}).status_code == 401
    assert client.get("/v1/forms", headers={"X-API-Key": k2["cle_en_clair"]}).status_code == 200


def test_admin_api_sans_cle_retourne_401() -> None:
    client = TestClient(app)
    r = client.get("/admin/api/comptes")
    assert r.status_code == 401


def test_admin_api_mauvaise_cle_retourne_401() -> None:
    client = TestClient(app)
    r = client.get("/admin/api/comptes", headers={"X-Admin-Key": "mauvaise-cle"})
    assert r.status_code == 401


# ── ADMIN-3 : suivi de consommation ──────────────────────────────────────────


def _fake_wav() -> bytes:
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00" * 320)
    return buf.getvalue()


def test_usage_comptabilise_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """L'usage est comptabilisé pour les appels effectués avec une clé DB."""
    from unittest.mock import patch
    from app.schemas.forms import Champ, Consultation

    def _consultation_complete():
        return Consultation(
            nom_patient=Champ(valeur="Martin", confiance="confiant"),
            prenom_patient=Champ(valeur="Jean", confiance="confiant"),
            date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
            motif=Champ(valeur="Céphalées", confiance="confiant"),
            diagnostic=Champ(valeur="Migraine", confiance="confiant"),
        )

    client = TestClient(app)
    compte = _creer_compte(client)
    cle = _creer_cle(client, compte["id"])["cle_en_clair"]

    with (
        patch("app.routers.sessions.transcrire", return_value="test"),
        patch("app.routers.sessions.extraire", return_value=_consultation_complete()),
        patch("app.services.clarification.synthetiser", return_value=_fake_wav()),
    ):
        r = client.post(
            "/v1/sessions",
            data={"form_id": "consultation_v1"},
            files={"audio": ("t.wav", _fake_wav(), "audio/wav")},
            headers={"X-API-Key": cle},
        )
    assert r.status_code == 200

    # Vérification de l'usage
    r_usage = client.get(
        f"/admin/api/usage?compte_id={compte['id']}", headers=ADMIN_HEADERS
    )
    assert r_usage.status_code == 200
    stats = r_usage.json()
    assert len(stats) == 1
    assert stats[0]["total_sessions"] == 1
    assert stats[0]["total_clarifications"] == 0


def test_usage_vide_sans_appels() -> None:
    client = TestClient(app)
    compte = _creer_compte(client)
    r = client.get(f"/admin/api/usage?compte_id={compte['id']}", headers=ADMIN_HEADERS)
    assert r.status_code == 200
    stats = r.json()
    assert stats[0]["total_sessions"] == 0
    assert stats[0]["total_clarifications"] == 0


# ── ADMIN-4 : portail web ─────────────────────────────────────────────────────


def test_page_connexion_accessible() -> None:
    client = TestClient(app, follow_redirects=False)
    r = client.get("/admin/connexion")
    assert r.status_code == 200
    assert "mot_de_passe" in r.text


def test_connexion_mauvais_mot_de_passe() -> None:
    client = TestClient(app, follow_redirects=False)
    r = client.post("/admin/connexion", data={"mot_de_passe": "mauvais"})
    assert r.status_code == 401
    assert "incorrect" in r.text.lower()


def test_connexion_bon_mot_de_passe_redirige() -> None:
    client = TestClient(app, follow_redirects=False)
    r = client.post("/admin/connexion", data={"mot_de_passe": TEST_ADMIN_PASSWORD})
    assert r.status_code == 302
    assert r.headers["location"] == "/admin/"


def test_dashboard_non_connecte_redirige() -> None:
    client = TestClient(app, follow_redirects=False)
    r = client.get("/admin/")
    assert r.status_code == 302
    assert "connexion" in r.headers["location"]


def test_parcours_login_dashboard_rotation() -> None:
    """Parcours principal : login → dashboard → création/révocation de clé."""
    with TestClient(app, follow_redirects=True) as client:
        # 1. Créer un compte via API
        compte = _creer_compte(client)
        compte_id = compte["id"]

        # 2. Login
        r_login = client.post("/admin/connexion", data={"mot_de_passe": TEST_ADMIN_PASSWORD})
        assert r_login.status_code == 200  # redirigé vers dashboard
        assert "Tableau de bord" in r_login.text

        # 3. Dashboard accessible après login
        r_dash = client.get("/admin/")
        assert r_dash.status_code == 200
        assert "Acme" in r_dash.text

        # 4. Page de gestion des clés
        r_keys = client.get(f"/admin/comptes/{compte_id}/cles")
        assert r_keys.status_code == 200

        # 5. Générer une clé via l'UI
        r_gen = client.post(f"/admin/comptes/{compte_id}/cles")
        assert r_gen.status_code == 200
        assert "Nouvelle clé créée" in r_gen.text

        # 6. Déconnexion
        r_logout = client.get("/admin/deconnexion")
        assert r_logout.status_code == 200  # redirigé vers /admin/connexion

        # 7. Dashboard inaccessible après déconnexion
        r_dash2 = client.get("/admin/", follow_redirects=False)
        assert r_dash2.status_code == 302


def test_catalogue_formulaires_connecte() -> None:
    with TestClient(app, follow_redirects=True) as client:
        client.post("/admin/connexion", data={"mot_de_passe": TEST_ADMIN_PASSWORD})
        r = client.get("/admin/formulaires")
        assert r.status_code == 200
        assert "consultation_v1" in r.text
        assert "rapport_chirurgie_v1" in r.text

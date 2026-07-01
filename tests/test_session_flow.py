"""Tests du store de sessions (SESS-1) et du flux complet (SESS-2/3/4)."""

from __future__ import annotations

import base64
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.schemas.forms import Champ, Consultation
from app.sessions.store import (
    Session,
    creer_session,
    fermer_session,
    get_session,
    mettre_a_jour_session,
    vider_sessions,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


from tests.conftest import TEST_API_KEY

HEADERS = {"X-API-Key": TEST_API_KEY}


@pytest.fixture(autouse=True)
def reset_store() -> None:
    """Vide le store avant chaque test."""
    vider_sessions()


def _consultation_complete() -> Consultation:
    return Consultation(
        nom_patient=Champ(valeur="Martin", confiance="confiant"),
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
        motif=Champ(valeur="Céphalées", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine", confiance="confiant"),
    )


def _consultation_incomplete() -> Consultation:
    return Consultation(
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
        motif=Champ(valeur="Céphalées", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine", confiance="confiant"),
    )


# ── SESS-1 : store ────────────────────────────────────────────────────────────


def test_creer_session_retourne_session_valide() -> None:
    form = _consultation_incomplete()
    session = creer_session("consultation_v1", form, "nom_patient")
    assert session.session_id
    assert session.form_id == "consultation_v1"
    assert session.champ_en_attente == "nom_patient"
    assert session.statut == "clarification"


def test_get_session_existante() -> None:
    form = _consultation_incomplete()
    session = creer_session("consultation_v1", form, "nom_patient")
    recuperee = get_session(session.session_id)
    assert recuperee is not None
    assert recuperee.session_id == session.session_id


def test_get_session_inconnue_retourne_none() -> None:
    assert get_session("session-inexistante") is None


def test_mettre_a_jour_session() -> None:
    form = _consultation_incomplete()
    session = creer_session("consultation_v1", form, "nom_patient")
    form_mis_a_jour = Consultation(
        nom_patient=Champ(valeur="Martin", confiance="confiant"),
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
        motif=Champ(valeur="Céphalées", confiance="confiant"),
    )
    mise_a_jour = mettre_a_jour_session(session.session_id, form_mis_a_jour, "diagnostic")
    assert mise_a_jour is not None
    assert mise_a_jour.champ_en_attente == "diagnostic"
    assert mise_a_jour.formulaire_partiel["nom_patient"]["valeur"] == "Martin"


def test_fermer_session() -> None:
    form = _consultation_incomplete()
    session = creer_session("consultation_v1", form, "nom_patient")
    fermer_session(session.session_id)
    assert get_session(session.session_id) is None


def test_session_expiree_non_renvoyee(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une session dont le TTL est dépassé doit retourner None."""
    form = _consultation_incomplete()
    session = creer_session("consultation_v1", form, "nom_patient")

    # Simule une session créée il y a 31 minutes (TTL = 30 min par défaut)
    from app.sessions import store as store_module

    old_time = datetime.now(tz=timezone.utc) - timedelta(minutes=31)
    session.mis_a_jour_le = old_time
    store_module._sessions[session.session_id] = session

    assert get_session(session.session_id) is None


# ── SESS-2 : POST /v1/sessions ────────────────────────────────────────────────


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


def _client_avec_mocks(
    transcription: str,
    formulaire: Consultation,
) -> TestClient:
    """Retourne un TestClient avec STT/extraction/TTS mockés."""
    from app.main import app
    return TestClient(app)


@pytest.fixture()
def mocks_pipeline(monkeypatch: pytest.MonkeyPatch):
    """Fixture qui mocke STT, extraction et TTS (piper via clarification)."""
    with (
        patch("app.routers.sessions.transcrire", return_value="transcription test"),
        patch("app.routers.sessions.extraire") as mock_extraire,
        patch("app.services.clarification.synthetiser", return_value=_fake_wav()),
    ):
        yield mock_extraire


def test_post_sessions_formulaire_complet(mocks_pipeline: MagicMock) -> None:
    """POST /v1/sessions avec formulaire complet doit retourner statut 'termine'."""
    from app.main import app

    mocks_pipeline.return_value = _consultation_complete()
    client = TestClient(app)

    wav = _fake_wav()
    response = client.post(
        "/v1/sessions",
        data={"form_id": "consultation_v1"},
        files={"audio": ("test.wav", wav, "audio/wav")},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["statut"] == "termine"
    assert "formulaire" in data


def test_post_sessions_formulaire_incomplet(mocks_pipeline: MagicMock) -> None:
    """POST /v1/sessions avec formulaire incomplet doit retourner 'clarification'."""
    from app.main import app

    mocks_pipeline.return_value = _consultation_incomplete()
    client = TestClient(app)

    wav = _fake_wav()
    response = client.post(
        "/v1/sessions",
        data={"form_id": "consultation_v1"},
        files={"audio": ("test.wav", wav, "audio/wav")},
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["statut"] == "clarification"
    assert "session_id" in data
    assert "question_texte" in data
    assert "question_audio" in data
    assert "champs_restants" in data


def test_post_sessions_form_id_inconnu() -> None:
    """POST /v1/sessions avec form_id inconnu doit retourner 404."""
    from app.main import app

    client = TestClient(app)
    wav = _fake_wav()
    response = client.post(
        "/v1/sessions",
        data={"form_id": "formulaire_inexistant"},
        files={"audio": ("test.wav", wav, "audio/wav")},
        headers=HEADERS,
    )
    assert response.status_code == 404


def test_post_sessions_stt_echoue_retourne_503() -> None:
    """Un échec de transcription (STTError) doit remonter en 503, pas produire un formulaire vide."""
    from app.main import app
    from app.services.stt import STTError

    client = TestClient(app)
    wav = _fake_wav()
    with patch(
        "app.routers.sessions.transcrire",
        side_effect=STTError("modèle indisponible"),
    ):
        response = client.post(
            "/v1/sessions",
            data={"form_id": "consultation_v1"},
            files={"audio": ("test.wav", wav, "audio/wav")},
            headers=HEADERS,
        )
    assert response.status_code == 503
    assert response.json()["erreur"] == "service_indisponible"


def test_post_sessions_extraction_echoue_retourne_503() -> None:
    """Un échec d'extraction LLM doit remonter en 503, pas en 500."""
    from app.main import app
    from app.services.extraction import ExtractionError

    client = TestClient(app)
    wav = _fake_wav()
    with (
        patch("app.routers.sessions.transcrire", return_value="texte transcrit"),
        patch("app.routers.sessions.extraire", side_effect=ExtractionError("LLM injoignable")),
    ):
        response = client.post(
            "/v1/sessions",
            data={"form_id": "consultation_v1"},
            files={"audio": ("test.wav", wav, "audio/wav")},
            headers=HEADERS,
        )
    assert response.status_code == 503
    assert response.json()["erreur"] == "service_indisponible"


# ── SESS-3 : POST /v1/sessions/{id}/repondre ─────────────────────────────────


def test_repondre_complete_la_session(mocks_pipeline: MagicMock) -> None:
    """POST /repondre avec réponse complétant le formulaire → 'termine'."""
    from app.main import app

    # Crée d'abord une session incomplète
    mocks_pipeline.return_value = _consultation_incomplete()
    client = TestClient(app)
    wav = _fake_wav()
    r1 = client.post(
        "/v1/sessions",
        data={"form_id": "consultation_v1"},
        files={"audio": ("test.wav", wav, "audio/wav")},
        headers=HEADERS,
    )
    session_id = r1.json()["session_id"]

    # Répond avec le formulaire complet cette fois
    mocks_pipeline.return_value = _consultation_complete()
    r2 = client.post(
        f"/v1/sessions/{session_id}/repondre",
        files={"audio": ("reponse.wav", wav, "audio/wav")},
        headers=HEADERS,
    )
    assert r2.status_code == 200
    assert r2.json()["statut"] == "termine"


def test_clarification_abandonne_champ_apres_max_tentatives() -> None:
    """Garde-fou anti-boucle : un champ jamais extrait est abandonné après MAX
    tentatives → la session se termine (champ laissé 'manquant' pour vérif humaine)."""
    from app.main import app
    from app.routers.sessions import MAX_TENTATIVES_PAR_CHAMP

    client = TestClient(app)
    wav = _fake_wav()
    # L'extraction renvoie toujours un formulaire où nom_patient reste manquant.
    incomplet = _consultation_incomplete()
    with (
        patch("app.routers.sessions.transcrire", return_value="réponse"),
        patch("app.routers.sessions.extraire", return_value=incomplet),
        patch("app.services.clarification.synthetiser", return_value=_fake_wav()),
    ):
        r = client.post(
            "/v1/sessions",
            data={"form_id": "consultation_v1"},
            files={"audio": ("t.wav", wav, "audio/wav")},
            headers=HEADERS,
        )
        assert r.json()["statut"] == "clarification"
        sid = r.json()["session_id"]

        statut = None
        for _ in range(MAX_TENTATIVES_PAR_CHAMP + 2):  # borne haute : doit finir avant
            r = client.post(
                f"/v1/sessions/{sid}/repondre",
                files={"audio": ("a.wav", wav, "audio/wav")},
                headers=HEADERS,
            )
            statut = r.json()["statut"]
            if statut == "termine":
                break

        assert statut == "termine"
        # le champ jamais extrait reste "manquant" (à compléter par l'humain)
        assert r.json()["formulaire"]["nom_patient"]["confiance"] == "manquant"


def test_repondre_session_inconnue_retourne_404() -> None:
    """POST /repondre sur session inexistante → 404."""
    from app.main import app

    client = TestClient(app)
    wav = _fake_wav()
    response = client.post(
        "/v1/sessions/session-inexistante/repondre",
        files={"audio": ("test.wav", wav, "audio/wav")},
        headers=HEADERS,
    )
    assert response.status_code == 404


# ── SESS-4 : GET /v1/sessions/{id} ───────────────────────────────────────────


def test_get_session_endpoint(mocks_pipeline: MagicMock) -> None:
    """GET /v1/sessions/{id} doit retourner l'état de la session."""
    from app.main import app

    mocks_pipeline.return_value = _consultation_incomplete()
    client = TestClient(app)
    wav = _fake_wav()
    r1 = client.post(
        "/v1/sessions",
        data={"form_id": "consultation_v1"},
        files={"audio": ("test.wav", wav, "audio/wav")},
        headers=HEADERS,
    )
    session_id = r1.json()["session_id"]

    r2 = client.get(f"/v1/sessions/{session_id}", headers=HEADERS)
    assert r2.status_code == 200
    data = r2.json()
    assert data["session_id"] == session_id
    assert data["statut"] == "clarification"
    assert "formulaire_partiel" in data
    assert "champs_restants" in data


def test_get_session_inconnue_retourne_404() -> None:
    """GET /v1/sessions/{id} sur id inconnu → 404."""
    from app.main import app

    client = TestClient(app)
    response = client.get("/v1/sessions/session-inexistante", headers=HEADERS)
    assert response.status_code == 404

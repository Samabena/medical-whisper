"""Tests du service de clarification (CLAR-1 + CLAR-2) — TTS mocké."""

from __future__ import annotations

import wave
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.forms import Champ, Consultation, DossierMedical, RapportChirurgie
from app.services.clarification import (
    ChampAClarifier,
    analyser,
    formuler_question_texte,
    generer_question_audio,
)


# ── CLAR-1 : analyser() ───────────────────────────────────────────────────────


def test_analyser_formulaire_complet_retourne_vide() -> None:
    """Un formulaire complet (tous champs obligatoires confiants) → liste vide."""
    form = Consultation(
        nom_patient=Champ(valeur="Martin", confiance="confiant"),
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
        motif=Champ(valeur="Céphalées", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine", confiance="confiant"),
    )
    assert analyser(form) == []


def test_analyser_champ_obligatoire_manquant() -> None:
    """Un champ obligatoire manquant doit apparaître dans la liste."""
    form = Consultation(
        nom_patient=Champ(valeur=None, confiance="manquant"),
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
        motif=Champ(valeur="Céphalées", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine", confiance="confiant"),
    )
    champs = analyser(form)
    noms = [c.nom for c in champs]
    assert "nom_patient" in noms
    assert all(c.raison == "manquant" for c in champs if c.nom == "nom_patient")


def test_analyser_obligatoires_avant_incertains() -> None:
    """Les champs obligatoires manquants doivent précéder les incertains."""
    form = Consultation(
        nom_patient=Champ(valeur=None, confiance="manquant"),    # obligatoire
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
        motif=Champ(valeur="Céphalées", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine ?", confiance="incertain"),  # incertain
    )
    champs = analyser(form)
    raisons = [c.raison for c in champs]
    # Le "manquant" doit être avant "incertain"
    idx_manquant = next(i for i, r in enumerate(raisons) if r == "manquant")
    idx_incertain = next(i for i, r in enumerate(raisons) if r == "incertain")
    assert idx_manquant < idx_incertain


def test_analyser_champ_optionnel_manquant_ignore() -> None:
    """Un champ optionnel manquant ne doit pas apparaître dans la liste."""
    form = Consultation(
        nom_patient=Champ(valeur="Martin", confiance="confiant"),
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
        motif=Champ(valeur="Céphalées", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine", confiance="confiant"),
        ordonnance=Champ(valeur=None, confiance="manquant"),  # optionnel
    )
    champs = analyser(form)
    assert not any(c.nom == "ordonnance" for c in champs)


def test_analyser_rapport_chirurgie_plusieurs_manquants() -> None:
    """Plusieurs champs obligatoires manquants doivent tous apparaître."""
    form = RapportChirurgie()  # tout manquant par défaut
    champs = analyser(form)
    noms = {c.nom for c in champs}
    assert "nom_patient" in noms
    assert "date_intervention" in noms
    assert "type_anesthesie" in noms
    assert "saignement" in noms


def test_analyser_dossier_medical_complet() -> None:
    form = DossierMedical(
        nom_patient=Champ(valeur="Leroy", confiance="confiant"),
        prenom_patient=Champ(valeur="Sophie", confiance="confiant"),
        date_naissance=Champ(valeur="1985-04-22", confiance="confiant"),
    )
    assert analyser(form) == []


# ── CLAR-2 : formuler_question_texte() + generer_question_audio() ─────────────


def test_formuler_question_champ_connu() -> None:
    """Un champ avec gabarit doit retourner la question associée."""
    champ = ChampAClarifier(nom="date_intervention", raison="manquant")
    question = formuler_question_texte(champ)
    assert "date" in question.lower() and "intervention" in question.lower()


def test_formuler_question_champ_inconnu() -> None:
    """Un champ sans gabarit doit retourner la question générique."""
    champ = ChampAClarifier(nom="champ_inconnu_xyz", raison="manquant")
    question = formuler_question_texte(champ)
    assert "champ_inconnu_xyz" in question


def test_generer_question_audio_retourne_texte_et_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    """generer_question_audio() doit retourner (texte, bytes WAV)."""

    def fake_synthetiser(texte: str) -> bytes:
        return b"RIFF\x00\x00\x00\x00WAVEfmt "  # en-tête WAV minimal

    with patch("app.services.clarification.synthetiser", side_effect=fake_synthetiser):
        form = Consultation(
            nom_patient=Champ(valeur=None, confiance="manquant"),
            prenom_patient=Champ(valeur="Jean", confiance="confiant"),
            date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
            motif=Champ(valeur="Céphalées", confiance="confiant"),
            diagnostic=Champ(valeur="Migraine", confiance="confiant"),
        )
        texte, audio = generer_question_audio(form)

    assert isinstance(texte, str) and len(texte) > 0
    assert isinstance(audio, bytes) and len(audio) > 0


def test_generer_question_audio_formulaire_complet_leve_erreur() -> None:
    """generer_question_audio() sur formulaire complet doit lever ValueError."""
    form = Consultation(
        nom_patient=Champ(valeur="Martin", confiance="confiant"),
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
        motif=Champ(valeur="Céphalées", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine", confiance="confiant"),
    )
    with pytest.raises(ValueError, match="complet"):
        generer_question_audio(form)

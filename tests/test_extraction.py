"""Tests du service d'extraction (STW-1) — LLM mocké."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.forms import Champ, Consultation, RapportChirurgie, TypeAnesthesie, NiveauSaignement
from app.services.extraction import _fusionner, extraire


def _consultation_complete() -> Consultation:
    return Consultation(
        nom_patient=Champ(valeur="Martin", confiance="confiant"),
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
        motif=Champ(valeur="Céphalées", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine", confiance="confiant"),
    )


def _mock_chain(retour: object) -> MagicMock:
    """Crée un mock de chain LLM retournant retour sur invoke()."""
    chain = MagicMock()
    chain.invoke.return_value = retour
    llm = MagicMock()
    llm.with_structured_output.return_value = chain
    return llm


# ── Tests unitaires ───────────────────────────────────────────────────────────


def test_extraire_retourne_instance_pydantic() -> None:
    """extraire() doit retourner une instance du modèle Pydantic correct."""
    attendu = _consultation_complete()
    mock_llm = _mock_chain(attendu)

    with patch("app.services.extraction.get_llm", return_value=mock_llm):
        resultat = extraire("Jean Martin consulte pour des céphalées.", "consultation_v1")

    assert isinstance(resultat, Consultation)
    assert resultat.nom_patient.valeur == "Martin"


def test_extraire_avec_partiel_preserve_champs_confiants() -> None:
    """extraire() avec formulaire_partiel ne doit pas écraser les champs 'confiant'."""
    partiel = Consultation(
        nom_patient=Champ(valeur="Martin", confiance="confiant"),
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine", confiance="manquant"),
    )
    nouveau = Consultation(
        nom_patient=Champ(valeur="Dupont", confiance="confiant"),  # ne doit PAS écraser
        prenom_patient=Champ(valeur="Pierre", confiance="confiant"),  # ne doit PAS écraser
        diagnostic=Champ(valeur="Migraine chronique", confiance="confiant"),
    )
    mock_llm = _mock_chain(nouveau)

    with patch("app.services.extraction.get_llm", return_value=mock_llm):
        resultat = extraire("diagnostic : migraine chronique", "consultation_v1", partiel)

    assert isinstance(resultat, Consultation)
    assert resultat.nom_patient.valeur == "Martin"     # conservé
    assert resultat.prenom_patient.valeur == "Jean"    # conservé
    assert resultat.diagnostic.valeur == "Migraine chronique"  # nouveau


def test_extraire_valeurs_plates_derive_confiance() -> None:
    """Cas réel : le LLM renvoie des valeurs PLATES → on dérive {valeur, confiance}."""
    from types import SimpleNamespace

    plat = SimpleNamespace(
        nom_patient="Dupont",
        prenom_patient="Jean",
        date_consultation="2026-06-12",
        motif="céphalées",
        diagnostic="migraine",
        date_naissance=None,
        antecedents=None,
        allergies=None,
        traitement_en_cours=None,
        ordonnance=None,
    )
    mock_llm = _mock_chain(plat)

    with patch("app.services.extraction.get_llm", return_value=mock_llm):
        resultat = extraire("dictée", "consultation_v1")

    assert isinstance(resultat, Consultation)
    # valeur présente -> confiance dérivée "confiant"
    assert resultat.nom_patient.valeur == "Dupont"
    assert resultat.nom_patient.confiance == "confiant"
    assert resultat.diagnostic.valeur == "migraine"
    assert resultat.diagnostic.confiance == "confiant"
    # champ non fourni -> reste "manquant"
    assert resultat.antecedents.confiance == "manquant"
    # défaut pré-rempli conservé quand le champ n'est pas extrait
    assert resultat.allergies.valeur == "Aucune connue"


def test_extraire_retry_sur_echec() -> None:
    """extraire() doit retenter une fois avant de lever ValueError."""
    chain = MagicMock()
    chain.invoke.side_effect = RuntimeError("LLM indisponible")
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = chain

    with patch("app.services.extraction.get_llm", return_value=mock_llm):
        with pytest.raises(ValueError, match="2 tentatives"):
            extraire("test", "consultation_v1")

    assert chain.invoke.call_count == 2


def test_extraire_succes_au_second_essai() -> None:
    """extraire() doit réussir si le 2e essai est valide."""
    attendu = _consultation_complete()
    chain = MagicMock()
    chain.invoke.side_effect = [RuntimeError("erreur transitoire"), attendu]
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = chain

    with patch("app.services.extraction.get_llm", return_value=mock_llm):
        resultat = extraire("test", "consultation_v1")

    assert isinstance(resultat, Consultation)


# ── Tests unitaires : fusion ──────────────────────────────────────────────────


def test_fusionner_preserves_champs_confiants() -> None:
    """_fusionner() doit garder les valeurs confiantes du partiel."""
    partiel = Consultation(
        nom_patient=Champ(valeur="Ancien", confiance="confiant"),
        diagnostic=Champ(valeur=None, confiance="manquant"),
    )
    nouveau = Consultation(
        nom_patient=Champ(valeur="Nouveau", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine", confiance="confiant"),
    )
    fusionne = _fusionner(partiel, nouveau)
    assert isinstance(fusionne, Consultation)
    assert fusionne.nom_patient.valeur == "Ancien"    # conservé
    assert fusionne.diagnostic.valeur == "Migraine"   # du nouveau


def test_fusionner_complete_champs_manquants() -> None:
    """_fusionner() doit compléter les champs 'manquant' avec le nouveau."""
    partiel = Consultation(
        nom_patient=Champ(valeur=None, confiance="manquant"),
    )
    nouveau = Consultation(
        nom_patient=Champ(valeur="Martin", confiance="confiant"),
    )
    fusionne = _fusionner(partiel, nouveau)
    assert fusionne.nom_patient.valeur == "Martin"

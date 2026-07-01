"""Tests des schémas Pydantic (FORM-1) et du catalogue (FORM-2)."""

import pytest
from pydantic import ValidationError

from app.catalog.forms_catalog import (
    get_champs_obligatoires,
    get_form_ids,
    get_form_model,
)
from app.schemas.forms import (
    Champ,
    Consultation,
    DossierMedical,
    NiveauSaignement,
    RapportChirurgie,
    TypeAnesthesie,
)

# ── FORM-1 : instanciation des modèles ────────────────────────────────────────


def test_consultation_valide() -> None:
    """Consultation doit s'instancier avec des données valides."""
    form = Consultation(
        nom_patient=Champ(valeur="Martin", confiance="confiant"),
        prenom_patient=Champ(valeur="Jean", confiance="confiant"),
        date_consultation=Champ(valeur="2024-06-01", confiance="confiant"),
        motif=Champ(valeur="Céphalées", confiance="confiant"),
        diagnostic=Champ(valeur="Migraine sans aura", confiance="confiant"),
    )
    assert form.nom_patient.valeur == "Martin"
    assert form.allergies.valeur == "Aucune connue"  # défaut
    assert form.allergies.confiance == "confiant"
    assert "nom_patient" in Consultation.CHAMPS_OBLIGATOIRES


def test_consultation_champs_vides_par_defaut() -> None:
    """Un Consultation vide doit avoir tous les champs 'manquant' sauf allergies."""
    form = Consultation()
    assert form.nom_patient.confiance == "manquant"
    assert form.nom_patient.valeur is None
    assert form.allergies.valeur == "Aucune connue"


def test_rapport_chirurgie_valide() -> None:
    """RapportChirurgie doit s'instancier avec des données valides incluant les enums."""
    form = RapportChirurgie(
        nom_patient=Champ(valeur="Dupont", confiance="confiant"),
        prenom_patient=Champ(valeur="Marie", confiance="confiant"),
        date_intervention=Champ(valeur="2024-03-10", confiance="confiant"),
        type_intervention=Champ(valeur="Appendicectomie", confiance="confiant"),
        chirurgien=Champ(valeur="Dr. Bernard", confiance="confiant"),
        type_anesthesie=Champ(valeur=TypeAnesthesie.GENERALE, confiance="confiant"),
        saignement=Champ(valeur=NiveauSaignement.MINIME, confiance="confiant"),
    )
    assert form.type_anesthesie.valeur == TypeAnesthesie.GENERALE
    assert form.saignement.valeur == NiveauSaignement.MINIME
    assert form.complications.valeur == "Aucune"  # défaut


def test_rapport_chirurgie_type_anesthesie_invalide() -> None:
    """Un type_anesthesie invalide doit lever une ValidationError."""
    with pytest.raises(ValidationError):
        RapportChirurgie(
            type_anesthesie=Champ(valeur="invalide", confiance="confiant")
        )


def test_dossier_medical_valide() -> None:
    """DossierMedical doit s'instancier avec des données valides."""
    form = DossierMedical(
        nom_patient=Champ(valeur="Leroy", confiance="confiant"),
        prenom_patient=Champ(valeur="Sophie", confiance="confiant"),
        date_naissance=Champ(valeur="1985-04-22", confiance="confiant"),
    )
    assert form.nom_patient.valeur == "Leroy"
    assert form.allergies.valeur == "Aucune connue"
    assert "nom_patient" in DossierMedical.CHAMPS_OBLIGATOIRES


# ── FORM-2 : catalogue ────────────────────────────────────────────────────────


def test_get_form_ids_retourne_trois_formulaires() -> None:
    """Le catalogue doit exposer les 3 form_id définis."""
    ids = get_form_ids()
    assert "consultation_v1" in ids
    assert "rapport_chirurgie_v1" in ids
    assert "dossier_medical_v1" in ids


def test_get_form_model_consultation() -> None:
    modele = get_form_model("consultation_v1")
    assert modele is Consultation


def test_get_form_model_rapport_chirurgie() -> None:
    modele = get_form_model("rapport_chirurgie_v1")
    assert modele is RapportChirurgie


def test_get_form_model_dossier_medical() -> None:
    modele = get_form_model("dossier_medical_v1")
    assert modele is DossierMedical


def test_get_form_model_inconnu_leve_keyerror() -> None:
    """Un form_id inconnu doit lever une KeyError avec message explicite."""
    with pytest.raises(KeyError, match="inconnu"):
        get_form_model("formulaire_inexistant")


def test_get_champs_obligatoires_consultation() -> None:
    obligatoires = get_champs_obligatoires("consultation_v1")
    assert "nom_patient" in obligatoires
    assert "diagnostic" in obligatoires
    assert "ordonnance" not in obligatoires  # optionnel


def test_get_champs_obligatoires_rapport_chirurgie() -> None:
    obligatoires = get_champs_obligatoires("rapport_chirurgie_v1")
    assert "date_intervention" in obligatoires
    assert "type_anesthesie" in obligatoires
    assert "anesthesiste" not in obligatoires  # optionnel

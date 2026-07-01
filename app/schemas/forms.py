"""Schémas Pydantic des formulaires médicaux."""

from __future__ import annotations

from enum import Enum
from typing import ClassVar, Generic, Literal, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Champ(BaseModel, Generic[T]):
    valeur: T | None = None
    confiance: Literal["confiant", "incertain", "manquant"] = "manquant"


def _champ() -> Champ:
    return Champ()


def _champ_allergies() -> Champ[str]:
    return Champ(valeur="Aucune connue", confiance="confiant")


def _champ_complications() -> Champ[str]:
    return Champ(valeur="Aucune", confiance="confiant")


class NiveauSaignement(str, Enum):
    AUCUN = "aucun"
    MINIME = "minime"
    MODERE = "modere"
    IMPORTANT = "important"


class TypeAnesthesie(str, Enum):
    GENERALE = "generale"
    LOCALE = "locale"
    LOCOREGIONALE = "locoregionale"
    RACHIANESTHESIE = "rachianesthesie"
    SEDATION = "sedation"


class Consultation(BaseModel):
    CHAMPS_OBLIGATOIRES: ClassVar[frozenset[str]] = frozenset(
        {"nom_patient", "prenom_patient", "date_consultation", "motif", "diagnostic"}
    )

    nom_patient: Champ[str] = _champ()
    prenom_patient: Champ[str] = _champ()
    date_naissance: Champ[str] = _champ()
    date_consultation: Champ[str] = _champ()
    motif: Champ[str] = _champ()
    antecedents: Champ[str] = _champ()
    allergies: Champ[str] = _champ_allergies()
    traitement_en_cours: Champ[str] = _champ()
    diagnostic: Champ[str] = _champ()
    ordonnance: Champ[str] = _champ()


class RapportChirurgie(BaseModel):
    CHAMPS_OBLIGATOIRES: ClassVar[frozenset[str]] = frozenset(
        {
            "nom_patient",
            "prenom_patient",
            "date_intervention",
            "type_intervention",
            "chirurgien",
            "type_anesthesie",
            "saignement",
        }
    )

    nom_patient: Champ[str] = _champ()
    prenom_patient: Champ[str] = _champ()
    date_naissance: Champ[str] = _champ()
    date_intervention: Champ[str] = _champ()
    type_intervention: Champ[str] = _champ()
    chirurgien: Champ[str] = _champ()
    type_anesthesie: Champ[TypeAnesthesie] = _champ()
    duree_minutes: Champ[int] = _champ()
    saignement: Champ[NiveauSaignement] = _champ()
    complications: Champ[str] = _champ_complications()
    notes_postoperatoires: Champ[str] = _champ()


class DossierMedical(BaseModel):
    CHAMPS_OBLIGATOIRES: ClassVar[frozenset[str]] = frozenset(
        {"nom_patient", "prenom_patient", "date_naissance"}
    )

    nom_patient: Champ[str] = _champ()
    prenom_patient: Champ[str] = _champ()
    date_naissance: Champ[str] = _champ()
    sexe: Champ[str] = _champ()
    adresse: Champ[str] = _champ()
    telephone: Champ[str] = _champ()
    medecin_traitant: Champ[str] = _champ()
    groupe_sanguin: Champ[str] = _champ()
    antecedents: Champ[str] = _champ()
    allergies: Champ[str] = _champ_allergies()
    traitements_en_cours: Champ[str] = _champ()

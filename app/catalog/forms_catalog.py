"""Catalogue des formulaires disponibles."""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel

from app.schemas.forms import Consultation, DossierMedical, RapportChirurgie

_CATALOGUE: dict[str, tuple[Type[BaseModel], str]] = {
    "consultation_v1": (Consultation, "Consultation médicale"),
    "rapport_chirurgie_v1": (RapportChirurgie, "Rapport opératoire"),
    "dossier_medical_v1": (DossierMedical, "Dossier patient"),
}


def get_form_ids() -> list[str]:
    return list(_CATALOGUE.keys())


def get_form_model(form_id: str) -> Type[BaseModel]:
    if form_id not in _CATALOGUE:
        raise KeyError(f"Formulaire inconnu : {form_id!r}. Disponibles : {get_form_ids()}")
    return _CATALOGUE[form_id][0]


def get_form_label(form_id: str) -> str:
    if form_id not in _CATALOGUE:
        raise KeyError(f"Formulaire inconnu : {form_id!r}.")
    return _CATALOGUE[form_id][1]


def get_champs_obligatoires(form_id: str) -> frozenset[str]:
    model = get_form_model(form_id)
    return model.CHAMPS_OBLIGATOIRES  # type: ignore[attr-defined]

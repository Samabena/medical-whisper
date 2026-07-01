"""Helpers de complétion du formulaire (fonctions pures)."""

from __future__ import annotations

from app.domain.entities import FormDefinition, FormState
from app.domain.value_objects import Confidence


def form_state_to_dict(state: FormState) -> dict:
    """Sérialise l'état `{champ: {valeur, confiance}}` pour le client / le stockage."""
    return {
        nom: {"valeur": fv.valeur, "confiance": fv.confiance.value}
        for nom, fv in state.values.items()
    }


def is_complete(form: FormDefinition, state: FormState) -> bool:
    """Vrai si tous les champs obligatoires sont remplis avec confiance « confiant »."""
    for nom in form.required_fields:
        fv = state.values.get(nom)
        if fv is None or fv.confiance is not Confidence.CONFIANT:
            return False
    return True

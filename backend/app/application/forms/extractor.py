"""Extracteur de formulaire (EXTR-8.1) — implémente FormExtractorPort.

Pipeline robuste (repris du v1) :
1. le LLM renvoie des **valeurs plates** (port `FlatExtractorPort`) ;
2. on **dérive** la structure `{valeur, confiance}` : valeur présente → « confiant » ;
3. on **fusionne** avec l'état partiel sans écraser un champ déjà « confiant ».

Logique pure et entièrement testable avec un faux extracteur plat.
"""

from __future__ import annotations

from app.application.ports.llm import FlatExtractorPort
from app.domain.entities import FieldValue, FormDefinition, FormState
from app.domain.value_objects import Confidence


def _valeur_presente(v: object) -> bool:
    if v is None:
        return False
    if isinstance(v, str) and not v.strip():
        return False
    return True


def _vers_form_state(form: FormDefinition, plat: dict[str, object]) -> FormState:
    state = FormState()
    for field in form.fields:
        v = plat.get(field.name)
        if _valeur_presente(v):
            state.values[field.name] = FieldValue(valeur=v, confiance=Confidence.CONFIANT)
    return state


def _fusionner(partiel: FormState, nouveau: FormState) -> FormState:
    """Conserve les champs déjà « confiant » du partiel ; complète avec le nouveau."""
    resultat = FormState(values=dict(partiel.values))
    for nom, fv in nouveau.values.items():
        existant = resultat.values.get(nom)
        if existant is not None and existant.confiance is Confidence.CONFIANT:
            continue
        resultat.values[nom] = fv
    return resultat


class FormExtractor:
    def __init__(self, flat: FlatExtractorPort) -> None:
        self._flat = flat

    async def update(self, transcript: str, form: FormDefinition, partiel: FormState) -> FormState:
        plat = await self._flat.extract(transcript, form)
        nouveau = _vers_form_state(form, plat)
        return _fusionner(partiel, nouveau)

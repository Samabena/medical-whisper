"""Extracteur plat déterministe (dev/test) — sans LLM ni GPU.

Remplit un champ quand le transcript contient « <nom|étiquette> <séparateur> <valeur> »
(séparateur : « : », « = », « est », « is »). Permet de tester la console live de bout
en bout en tapant des phrases simples (ex. « nom: Dupont, diagnostic: migraine »).
Pour l'extraction en langage naturel libre, utiliser le backend `ollama`.
"""

from __future__ import annotations

import re

from app.domain.entities import FormDefinition
from app.domain.value_objects import FieldType


def _coerce(valeur: str, type_: FieldType):
    valeur = valeur.strip()
    if type_ is FieldType.INT:
        m = re.search(r"-?\d+", valeur)
        return int(m.group()) if m else None
    if type_ is FieldType.NUMBER:
        m = re.search(r"-?\d+(?:[.,]\d+)?", valeur)
        return float(m.group().replace(",", ".")) if m else None
    if type_ is FieldType.BOOL:
        return valeur.lower() in {"oui", "yes", "true", "vrai", "1"}
    return valeur


class KeywordFlatExtractor:
    async def extract(self, transcript: str, form: FormDefinition) -> dict[str, object]:
        out: dict[str, object] = {}
        for f in form.fields:
            for token in (f.label, f.name):
                if not token:
                    continue
                motif = rf"{re.escape(token)}\s*(?::|=|\best\b|\bis\b)\s*([^,;.\n]+)"
                m = re.search(motif, transcript, re.IGNORECASE)
                if m:
                    valeur = _coerce(m.group(1), f.type)
                    if valeur is not None and valeur != "":
                        out[f.name] = valeur
                    break
        return out

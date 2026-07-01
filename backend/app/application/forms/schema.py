"""Sérialisation d'un formulaire en schéma exposable au client (fonction pure).

Réutilisé par la création de session (INT-5.1) et la découverte de formulaires (FORM-4.3).
"""

from __future__ import annotations

from app.domain.entities import FormDefinition


def form_schema(form: FormDefinition) -> dict:
    return {
        "form_id": form.form_id,
        "titre": form.titre,
        "version": form.version,
        "language": form.langue.value if form.langue else None,
        "fields": [
            {
                "name": f.name,
                "label": f.label,
                "type": f.type.value,
                "required": f.required,
                "enum_values": f.enum_values,
                "description": f.description,
            }
            for f in form.fields
        ],
    }

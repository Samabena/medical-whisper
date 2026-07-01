"""Construction du prompt et du schéma plat d'extraction depuis un FormDefinition.

Source unique (DRY) : la même `FormDefinition` produit le schéma JSON exposé au LLM et
les instructions d'extraction. La persona vocale (EPIC 4.2) réutilisera ces descriptions.
"""

from __future__ import annotations

from app.domain.entities import FormDefinition, FormField
from app.domain.value_objects import FieldType, Language

# FieldType → type de base JSON (tous les champs sont nullable : le LLM met null si absent).
_TYPE_JSON: dict[FieldType, str] = {
    FieldType.STRING: "string",
    FieldType.TEXT: "string",
    FieldType.DATE: "string",
    FieldType.INT: "integer",
    FieldType.NUMBER: "number",
    FieldType.BOOL: "boolean",
    FieldType.ENUM: "string",
}


def _description(field: FormField, langue: Language) -> str:
    desc = field.description or field.label
    if field.type is FieldType.DATE:
        desc += " (format AAAA-MM-JJ)" if langue is Language.FR else " (format YYYY-MM-DD)"
    if field.type is FieldType.ENUM:
        valeurs = ", ".join(field.enum_values)
        desc += (
            f" — valeurs autorisées : {valeurs}"
            if langue is Language.FR
            else f" — allowed values: {valeurs}"
        )
    return desc


def _langue(form: FormDefinition) -> Language:
    return form.langue or Language.FR


def build_flat_schema(form: FormDefinition) -> dict:
    """Schéma JSON (structured output) : un champ nullable par champ du formulaire."""
    langue = _langue(form)
    proprietes = {
        f.name: {"type": [_TYPE_JSON[f.type], "null"], "description": _description(f, langue)}
        for f in form.fields
    }
    return {"type": "object", "properties": proprietes}


def build_extraction_prompt(form: FormDefinition) -> str:
    """Instructions système pour le LLM d'extraction, dans la langue du formulaire."""
    langue = _langue(form)
    lignes = [f"- {f.name} : {_description(f, langue)}" for f in form.fields]
    champs = "\n".join(lignes)
    if langue is Language.FR:
        return (
            "Tu es un outil de transcription documentaire médicale utilisé par un soignant "
            "autorisé. Recopie fidèlement dans chaque champ l'information énoncée dans le texte "
            "(y compris nom et prénom du patient, données administratives normales). Pour chaque "
            "champ, reporte la valeur exactement telle qu'énoncée ; si l'information n'est PAS "
            "mentionnée, laisse le champ à null (n'invente rien).\n\nChamps :\n" + champs
        )
    return (
        "You are a medical documentation transcription tool used by an authorized clinician. "
        "Faithfully copy each stated piece of information into its field (including the patient's "
        "first and last name, which are normal administrative data). For each field, report the "
        "value exactly as stated; if the information is NOT mentioned, leave the field null "
        "(do not invent anything).\n\nFields:\n" + champs
    )


def build_hotwords(form: FormDefinition) -> list[str]:
    """Liste de hotwords (jargon médical) dérivée de la MÊME FormDefinition (DRY, FORM-4.2).

    Transmise à WhisperLive (`open(language, hotwords)`) pour biaiser la reconnaissance vers
    le vocabulaire du formulaire (labels de champs + valeurs d'énumération). Modifier un champ
    met donc à jour à la fois l'agent, le schéma d'extraction ET les hotwords, sans double saisie.

    On retient les **labels** (termes en langue naturelle) et les **valeurs d'enum** ; pas les
    `name` (identifiants snake_case sans intérêt pour le STT). Déduplication insensible à la
    casse en préservant l'ordre et la casse d'origine.
    """
    vus: set[str] = set()
    hotwords: list[str] = []
    for field_ in form.fields:
        candidats = [field_.label]
        if field_.type is FieldType.ENUM:
            candidats.extend(field_.enum_values)
        for terme in candidats:
            terme = (terme or "").strip()
            cle = terme.casefold()
            if terme and cle not in vus:
                vus.add(cle)
                hotwords.append(terme)
    return hotwords


def build_persona(form: FormDefinition) -> str:
    """Instructions de persona vocale (FORM-4.2), dérivées de la MÊME FormDefinition (DRY).

    Utilisée par l'agent live quand le compte n'a pas de persona propre : modifier un
    champ du formulaire change à la fois le schéma d'extraction ET la persona.
    """
    langue = _langue(form)
    requis = [f.label for f in form.fields if f.required]
    if langue is Language.FR:
        liste = ", ".join(requis) if requis else "(aucun champ obligatoire)"
        return (
            f"Tu es un assistant vocal médical qui aide un soignant à remplir le formulaire "
            f"« {form.titre} ». Parle français, pose des questions courtes, une à la fois, pour "
            f"obtenir les informations manquantes. Champs obligatoires : {liste}."
        )
    liste = ", ".join(requis) if requis else "(no required fields)"
    return (
        f"You are a medical voice assistant helping a clinician fill in the form "
        f"« {form.titre} ». Speak English, ask short questions, one at a time, to obtain the "
        f"missing information. Required fields: {liste}."
    )

"""EXTR-8.1 / FORM-4.2 — schéma plat et prompt d'extraction dérivés du formulaire."""

from __future__ import annotations

from app.application.forms.prompt_builder import (
    build_extraction_prompt,
    build_flat_schema,
    build_hotwords,
    build_persona,
)
from app.domain.entities import FormDefinition, FormField
from app.domain.value_objects import FieldType, Language


def _form(langue: Language | None = None) -> FormDefinition:
    return FormDefinition(
        account_id=1,
        form_id="f",
        titre="F",
        langue=langue,
        fields=[
            FormField("nom", "Nom", FieldType.STRING, required=True),
            FormField("date_n", "Date de naissance", FieldType.DATE),
            FormField("age", "Âge", FieldType.INT),
            FormField("sexe", "Sexe", FieldType.ENUM, enum_values=["m", "f"]),
        ],
    )


def test_schema_nullable_types_et_enrichissements():
    props = build_flat_schema(_form())["properties"]
    assert props["nom"]["type"] == ["string", "null"]
    assert props["age"]["type"] == ["integer", "null"]
    assert "AAAA-MM-JJ" in props["date_n"]["description"]   # FR par défaut
    assert "m, f" in props["sexe"]["description"]           # valeurs enum exposées


def test_prompt_dans_la_langue_du_formulaire():
    fr = build_extraction_prompt(_form(Language.FR))
    en = build_extraction_prompt(_form(Language.EN))
    assert "soignant" in fr and "null" in fr
    assert "clinician" in en and "YYYY-MM-DD" in en
    assert "- nom" in fr  # les champs sont listés


def test_persona_liste_les_champs_requis():
    fr = build_persona(_form(Language.FR))
    en = build_persona(_form(Language.EN))
    assert "Nom" in fr and "français" in fr   # label du champ requis + langue
    assert "Nom" in en and "English" in en


def test_hotwords_labels_et_valeurs_enum_dedupliques():
    # FORM-4.2 : les labels (jargon) et valeurs d'enum nourrissent les hotwords STT.
    mots = build_hotwords(_form())
    assert mots[0] == "Nom"  # ordre des champs préservé
    assert "Date de naissance" in mots and "Âge" in mots
    assert "Sexe" in mots and "m" in mots and "f" in mots  # label + valeurs enum
    assert "nom" not in mots  # les `name` snake_case ne sont pas des hotwords


def test_hotwords_deduplique_insensible_a_la_casse():
    form = FormDefinition(
        account_id=1,
        form_id="f",
        titre="F",
        fields=[
            FormField("a", "Tension", FieldType.STRING),
            FormField("b", "Statut", FieldType.ENUM, enum_values=["tension", "repos"]),
        ],
    )
    mots = build_hotwords(form)
    assert mots.count("Tension") + mots.count("tension") == 1  # un seul, casse d'origine
    assert "repos" in mots


def test_dry_meme_source_pour_schema_et_persona():
    # FORM-4.2 : un même champ alimente le schéma d'extraction ET la persona.
    form = FormDefinition(
        account_id=1,
        form_id="f",
        titre="F",
        fields=[FormField("diag", "Diagnostic principal", FieldType.STRING, required=True)],
    )
    assert "diag" in build_flat_schema(form)["properties"]
    assert "Diagnostic principal" in build_persona(form)

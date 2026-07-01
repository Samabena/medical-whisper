"""Extracteur déterministe `keyword` (dev/test, sans LLM)."""

from __future__ import annotations

from app.domain.entities import FormDefinition, FormField
from app.domain.value_objects import FieldType
from app.infrastructure.extraction.keyword_extractor import KeywordFlatExtractor


def _form() -> FormDefinition:
    return FormDefinition(
        account_id=1, form_id="f", titre="F",
        fields=[
            FormField("nom", "Nom", FieldType.STRING, required=True),
            FormField("age", "Âge", FieldType.INT),
            FormField("diagnostic", "Diagnostic", FieldType.STRING),
        ],
    )


async def test_extraction_par_separateurs():
    ex = KeywordFlatExtractor()
    out = await ex.extract("nom: Dupont, diagnostic = migraine, Âge est 42", _form())
    assert out["nom"] == "Dupont"
    assert out["diagnostic"] == "migraine"
    assert out["age"] == 42  # converti en entier


async def test_aucun_match():
    ex = KeywordFlatExtractor()
    assert await ex.extract("bonjour, rien de structuré ici", _form()) == {}


async def test_match_par_etiquette_ou_nom():
    ex = KeywordFlatExtractor()
    out = await ex.extract("Diagnostic: grippe", _form())
    assert out == {"diagnostic": "grippe"}

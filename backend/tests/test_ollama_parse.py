"""EXTR-8.1 — robustesse du parsing JSON des sorties LLM (gpt-oss enrobe parfois)."""

from __future__ import annotations

import pytest

from app.infrastructure.extraction.ollama_flat_extractor import _parse_json_objet


def test_json_simple():
    assert _parse_json_objet('{"a": 1, "b": null}') == {"a": 1, "b": None}


def test_bloc_markdown_json():
    contenu = '```json\n{\n  "patient_nom": "Jean"\n}\n```'
    assert _parse_json_objet(contenu) == {"patient_nom": "Jean"}


def test_bloc_markdown_sans_langage():
    assert _parse_json_objet('```\n{"x": 2}\n```') == {"x": 2}


def test_texte_autour_de_l_objet():
    contenu = 'Voici le résultat : {"motif": "migraine"} merci.'
    assert _parse_json_objet(contenu) == {"motif": "migraine"}


def test_contenu_non_json_leve():
    with pytest.raises(ValueError):
        _parse_json_objet("- patient_nom : Jean\n- age : 54")

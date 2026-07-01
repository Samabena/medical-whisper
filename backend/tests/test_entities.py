"""DATA-1.1 — invariants des entités du domaine."""

from __future__ import annotations

import pytest

from app.domain.entities import Account, FormDefinition, FormField
from app.domain.errors import ValidationError
from app.domain.value_objects import FieldType, Language


def test_champ_enum_exige_des_valeurs():
    with pytest.raises(ValidationError):
        FormField("sexe", "Sexe", FieldType.ENUM)  # pas de enum_values


def test_champ_non_enum_refuse_des_valeurs():
    with pytest.raises(ValidationError):
        FormField("nom", "Nom", FieldType.STRING, enum_values=["x"])


def test_formulaire_refuse_noms_dupliques():
    with pytest.raises(ValidationError):
        FormDefinition(
            account_id=1,
            form_id="f",
            titre="F",
            fields=[
                FormField("nom", "Nom", FieldType.STRING),
                FormField("nom", "Nom bis", FieldType.STRING),
            ],
        )


def test_required_fields_helper():
    form = FormDefinition(
        account_id=1,
        form_id="f",
        titre="F",
        fields=[
            FormField("a", "A", FieldType.STRING, required=True),
            FormField("b", "B", FieldType.STRING),
        ],
    )
    assert form.required_fields == ["a"]


def test_compte_defaut_francais():
    a = Account(nom="X", email_contact="x@ex.com")
    assert a.langue is Language.FR
    with pytest.raises(ValidationError):
        Account(nom="X", email_contact="")

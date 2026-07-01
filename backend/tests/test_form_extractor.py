"""EXTR-8.1 — FormExtractor : confiance, fusion incrémentale, valeurs vides ignorées."""

from __future__ import annotations

from app.application.forms.extractor import FormExtractor
from app.domain.entities import FormDefinition, FormField, FormState
from app.domain.value_objects import Confidence, FieldType


class FakeFlat:
    """Renvoie le 1er dict dont la clé est contenue dans le transcript."""

    def __init__(self, mapping: dict[str, dict]) -> None:
        self._m = mapping

    async def extract(self, transcript: str, form: FormDefinition) -> dict[str, object]:
        for cle, valeurs in self._m.items():
            if cle in transcript:
                return valeurs
        return {}


def _form() -> FormDefinition:
    return FormDefinition(
        account_id=1,
        form_id="f",
        titre="F",
        fields=[
            FormField("nom", "Nom", FieldType.STRING, required=True),
            FormField("age", "Âge", FieldType.INT),
            FormField("sexe", "Sexe", FieldType.ENUM, enum_values=["m", "f"]),
        ],
    )


async def test_valeur_presente_marquee_confiant():
    ex = FormExtractor(FakeFlat({"Martin": {"nom": "Martin"}}))
    st = await ex.update("le nom est Martin", _form(), FormState())
    assert st.values["nom"].valeur == "Martin"
    assert st.values["nom"].confiance is Confidence.CONFIANT
    assert "age" not in st.values  # champ absent → pas dans l'état


async def test_fusion_incrementale_sans_ecraser_le_confiant():
    ex = FormExtractor(
        FakeFlat({"nom Martin": {"nom": "Martin"}, "age 40": {"age": 40}, "rename": {"nom": "Autre"}})
    )
    form = _form()
    st = await ex.update("nom Martin", form, FormState())
    st = await ex.update("age 40", form, st)
    assert st.values["nom"].valeur == "Martin" and st.values["age"].valeur == 40

    # Une extraction ultérieure ne doit PAS écraser un champ déjà confiant.
    st = await ex.update("rename", form, st)
    assert st.values["nom"].valeur == "Martin"


async def test_valeur_vide_ignoree():
    ex = FormExtractor(FakeFlat({"x": {"nom": "   "}}))
    st = await ex.update("x", _form(), FormState())
    assert "nom" not in st.values

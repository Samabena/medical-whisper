"""Découverte des formulaires côté client (FORM-4.3) — uniquement les versions publiées."""

from __future__ import annotations

from app.application.ports.repositories import FormRepo
from app.domain.entities import FormDefinition
from app.domain.errors import NotFoundError
from app.domain.value_objects import FormStatus


def _dernieres_publiees(forms: list[FormDefinition]) -> dict[str, FormDefinition]:
    latest: dict[str, FormDefinition] = {}
    for f in forms:
        if f.statut is not FormStatus.PUBLISHED:
            continue
        courant = latest.get(f.form_id)
        if courant is None or f.version > courant.version:
            latest[f.form_id] = f
    return latest


class ListPublishedForms:
    def __init__(self, forms: FormRepo) -> None:
        self._forms = forms

    async def execute(self, account_id: int) -> list[FormDefinition]:
        tous = await self._forms.list_for_account(account_id)
        return list(_dernieres_publiees(tous).values())


class GetPublishedForm:
    def __init__(self, forms: FormRepo) -> None:
        self._forms = forms

    async def execute(self, account_id: int, form_id: str) -> FormDefinition:
        tous = await self._forms.list_for_account(account_id)
        form = _dernieres_publiees(tous).get(form_id)
        if form is None:
            raise NotFoundError(f"Formulaire {form_id!r} indisponible.")
        return form

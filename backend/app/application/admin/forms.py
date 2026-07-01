"""Cas d'usage du constructeur de formulaires (FORM-4.1).

Versionnage : un formulaire publié n'est plus modifié en place — toute édition d'un
formulaire publié crée une nouvelle version « draft » (la publiée reste intacte).
"""

from __future__ import annotations

from app.application.ports.repositories import FormRepo
from app.domain.entities import FormDefinition, FormField
from app.domain.errors import ConflictError, NotFoundError
from app.domain.value_objects import FormStatus, Language


class CreateForm:
    def __init__(self, forms: FormRepo) -> None:
        self._forms = forms

    async def execute(
        self,
        account_id: int,
        form_id: str,
        titre: str,
        fields: list[FormField],
        langue: Language | None = None,
    ) -> FormDefinition:
        if await self._forms.get(account_id, form_id) is not None:
            raise ConflictError(f"Le formulaire {form_id!r} existe déjà pour ce compte.")
        form = FormDefinition(  # __post_init__ valide (noms dupliqués, enum, etc.)
            account_id=account_id,
            form_id=form_id,
            titre=titre,
            fields=fields,
            langue=langue,
            version=1,
            statut=FormStatus.DRAFT,
        )
        return await self._forms.add(form)


class UpdateForm:
    def __init__(self, forms: FormRepo) -> None:
        self._forms = forms

    async def execute(
        self,
        account_id: int,
        form_id: str,
        *,
        titre: str | None = None,
        fields: list[FormField] | None = None,
        langue: Language | None = None,
    ) -> FormDefinition:
        current = await self._forms.get(account_id, form_id)
        if current is None:
            raise NotFoundError(f"Formulaire {form_id!r} introuvable.")

        titre_f = titre if titre is not None else current.titre
        fields_f = fields if fields is not None else current.fields
        langue_f = langue if langue is not None else current.langue

        if current.statut is FormStatus.DRAFT:
            maj = FormDefinition(
                account_id=account_id, form_id=form_id, titre=titre_f, fields=fields_f,
                langue=langue_f, version=current.version, statut=FormStatus.DRAFT, id=current.id,
            )
            return await self._forms.update(maj)

        # Publié → nouvelle version draft (la publiée reste intacte).
        nouvelle = FormDefinition(
            account_id=account_id, form_id=form_id, titre=titre_f, fields=fields_f,
            langue=langue_f, version=current.version + 1, statut=FormStatus.DRAFT,
        )
        return await self._forms.add(nouvelle)


class PublishForm:
    def __init__(self, forms: FormRepo) -> None:
        self._forms = forms

    async def execute(self, account_id: int, form_id: str) -> FormDefinition:
        current = await self._forms.get(account_id, form_id)
        if current is None:
            raise NotFoundError(f"Formulaire {form_id!r} introuvable.")
        if current.statut is FormStatus.PUBLISHED:
            return current
        current.statut = FormStatus.PUBLISHED
        return await self._forms.update(current)


class ListForms:
    def __init__(self, forms: FormRepo) -> None:
        self._forms = forms

    async def execute(self, account_id: int) -> list[FormDefinition]:
        return await self._forms.list_for_account(account_id)


class GetForm:
    def __init__(self, forms: FormRepo) -> None:
        self._forms = forms

    async def execute(self, account_id: int, form_id: str) -> FormDefinition:
        form = await self._forms.get(account_id, form_id)
        if form is None:
            raise NotFoundError(f"Formulaire {form_id!r} introuvable.")
        return form

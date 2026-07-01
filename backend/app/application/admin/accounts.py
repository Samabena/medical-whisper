"""Cas d'usage de gestion des comptes (ADM-3.1 / ADM-3.3)."""

from __future__ import annotations

from app.application.ports.repositories import AccountRepo
from app.domain.entities import Account
from app.domain.errors import ConflictError, NotFoundError
from app.domain.value_objects import Language


class CreateAccount:
    def __init__(self, accounts: AccountRepo) -> None:
        self._accounts = accounts

    async def execute(
        self,
        nom: str,
        email_contact: str,
        langue: Language = Language.FR,
        allowed_origins: list[str] | None = None,
    ) -> Account:
        if await self._accounts.get_by_email(email_contact):
            raise ConflictError(f"Un compte existe déjà pour {email_contact}.")
        compte = Account(
            nom=nom,
            email_contact=email_contact,
            langue=langue,
            allowed_origins=allowed_origins or [],
        )
        return await self._accounts.add(compte)


class ListAccounts:
    def __init__(self, accounts: AccountRepo) -> None:
        self._accounts = accounts

    async def execute(self) -> list[Account]:
        return await self._accounts.list()


class GetAccount:
    def __init__(self, accounts: AccountRepo) -> None:
        self._accounts = accounts

    async def execute(self, account_id: int) -> Account:
        compte = await self._accounts.get(account_id)
        if compte is None:
            raise NotFoundError(f"Compte {account_id} introuvable.")
        return compte


class UpdateAccount:
    """Met à jour langue (ADM-3.1) et persona/voix (ADM-3.3), nom, origines, activation."""

    def __init__(self, accounts: AccountRepo) -> None:
        self._accounts = accounts

    async def execute(
        self,
        account_id: int,
        *,
        nom: str | None = None,
        langue: Language | None = None,
        persona_prompt: str | None = None,
        voice_prompt: str | None = None,
        allowed_origins: list[str] | None = None,
        actif: bool | None = None,
    ) -> Account:
        compte = await self._accounts.get(account_id)
        if compte is None:
            raise NotFoundError(f"Compte {account_id} introuvable.")
        if nom is not None:
            compte.nom = nom
        if langue is not None:
            compte.langue = langue
        if persona_prompt is not None:
            compte.persona_prompt = persona_prompt
        if voice_prompt is not None:
            compte.voice_prompt = voice_prompt
        if allowed_origins is not None:
            compte.allowed_origins = allowed_origins
        if actif is not None:
            compte.actif = actif
        return await self._accounts.update(compte)

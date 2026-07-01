"""Cas d'usage de gestion des clés API (ADM-3.2).

Génération d'une clé haute entropie (clé en clair affichée une seule fois), stockage
haché, rotation (N clés actives) et révocation. Le hachage passe par le port `KeyHasher`.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from app.application.ports.repositories import AccountRepo, ApiKeyRepo
from app.application.ports.security import KeyHasher
from app.domain.entities import ApiKey
from app.domain.errors import NotFoundError

_PREFIX_LEN = 8


@dataclass(frozen=True)
class NouvelleCle:
    cle_claire: str   # affichée UNE seule fois
    key: ApiKey


class CreateApiKey:
    def __init__(self, accounts: AccountRepo, keys: ApiKeyRepo, hasher: KeyHasher) -> None:
        self._accounts = accounts
        self._keys = keys
        self._hasher = hasher

    async def execute(self, account_id: int, label: str = "Clé principale") -> NouvelleCle:
        if await self._accounts.get(account_id) is None:
            raise NotFoundError(f"Compte {account_id} introuvable.")
        cle_claire = secrets.token_urlsafe(32)
        key = ApiKey(
            account_id=account_id,
            key_prefix=cle_claire[:_PREFIX_LEN],
            key_hash=self._hasher.hash(cle_claire),
            label=label,
        )
        stored = await self._keys.add(key)
        return NouvelleCle(cle_claire=cle_claire, key=stored)


class ListApiKeys:
    def __init__(self, keys: ApiKeyRepo) -> None:
        self._keys = keys

    async def execute(self, account_id: int) -> list[ApiKey]:
        return await self._keys.list_for_account(account_id)


class RevokeApiKey:
    def __init__(self, keys: ApiKeyRepo) -> None:
        self._keys = keys

    async def execute(self, account_id: int, key_id: int) -> ApiKey:
        cles = await self._keys.list_for_account(account_id)
        if not any(k.id == key_id for k in cles):
            raise NotFoundError("Clé introuvable pour ce compte.")
        return await self._keys.revoke(key_id)

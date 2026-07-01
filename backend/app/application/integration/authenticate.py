"""Authentification d'un client par clé API (INT-5.1).

Résout le compte associé à une clé `X-API-Key`. La clé est hachée (port `KeyHasher`)
puis recherchée ; clé inconnue/révoquée ou compte inactif → `UnauthorizedError`.
"""

from __future__ import annotations

from app.application.ports.repositories import AccountRepo, ApiKeyRepo
from app.application.ports.security import KeyHasher
from app.domain.entities import Account
from app.domain.errors import UnauthorizedError


async def authenticate_api_key(
    cle_claire: str | None,
    accounts: AccountRepo,
    keys: ApiKeyRepo,
    hasher: KeyHasher,
) -> Account:
    if not cle_claire:
        raise UnauthorizedError("Clé API manquante.")
    cle = await keys.get_by_hash(hasher.hash(cle_claire))
    if cle is None or not cle.actif:
        raise UnauthorizedError("Clé API invalide ou révoquée.")
    compte = await accounts.get(cle.account_id)
    if compte is None or not compte.actif:
        raise UnauthorizedError("Compte inactif.")
    return compte

"""Fakes in-memory des ports de repository (DATA-1.2).

Réutilisés par les tests de cas d'usage (EPIC 3+) : ils honorent le même contrat que
les implémentations SQLAlchemy, sans base de données.
"""

from __future__ import annotations

from dataclasses import replace

from app.domain.entities import Account, ApiKey, FormDefinition, LiveSession, UsageRecord


class InMemoryAccountRepo:
    def __init__(self) -> None:
        self._items: dict[int, Account] = {}
        self._seq = 0

    async def add(self, account: Account) -> Account:
        self._seq += 1
        stored = replace(account, id=self._seq)
        self._items[self._seq] = stored
        return stored

    async def get(self, account_id: int) -> Account | None:
        return self._items.get(account_id)

    async def get_by_email(self, email: str) -> Account | None:
        return next((a for a in self._items.values() if a.email_contact == email), None)

    async def list(self) -> list[Account]:
        return list(self._items.values())

    async def update(self, account: Account) -> Account:
        self._items[account.id] = account
        return account


class InMemoryApiKeyRepo:
    def __init__(self) -> None:
        self._items: dict[int, ApiKey] = {}
        self._seq = 0

    async def add(self, key: ApiKey) -> ApiKey:
        self._seq += 1
        stored = replace(key, id=self._seq)
        self._items[self._seq] = stored
        return stored

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        return next((k for k in self._items.values() if k.key_hash == key_hash), None)

    async def list_for_account(self, account_id: int) -> list[ApiKey]:
        return [k for k in self._items.values() if k.account_id == account_id]

    async def revoke(self, key_id: int) -> ApiKey | None:
        k = self._items.get(key_id)
        if k is None:
            return None
        revoked = replace(k, actif=False)
        self._items[key_id] = revoked
        return revoked


class InMemoryFormRepo:
    def __init__(self) -> None:
        self._items: dict[int, FormDefinition] = {}
        self._seq = 0

    async def add(self, form: FormDefinition) -> FormDefinition:
        self._seq += 1
        stored = replace(form, id=self._seq)
        self._items[self._seq] = stored
        return stored

    async def get(self, account_id: int, form_id: str) -> FormDefinition | None:
        candidats = [
            f for f in self._items.values() if f.account_id == account_id and f.form_id == form_id
        ]
        return max(candidats, key=lambda f: f.version) if candidats else None

    async def list_for_account(self, account_id: int) -> list[FormDefinition]:
        return [f for f in self._items.values() if f.account_id == account_id]

    async def update(self, form: FormDefinition) -> FormDefinition:
        self._items[form.id] = form
        return form


class InMemorySessionRepo:
    def __init__(self) -> None:
        self._items: dict[str, LiveSession] = {}

    async def add(self, session: LiveSession) -> LiveSession:
        self._items[session.id] = session
        return session

    async def get(self, session_id: str) -> LiveSession | None:
        return self._items.get(session_id)

    async def update(self, session: LiveSession) -> LiveSession:
        self._items[session.id] = session
        return session


class InMemoryUsageRepo:
    def __init__(self) -> None:
        self._items: list[UsageRecord] = []

    async def record(self, usage: UsageRecord) -> UsageRecord:
        stored = replace(usage, id=len(self._items) + 1)
        self._items.append(stored)
        return stored

    async def count_by_endpoint(self, account_id: int) -> dict[str, int]:
        compteur: dict[str, int] = {}
        for u in self._items:
            if u.account_id == account_id:
                compteur[u.endpoint] = compteur.get(u.endpoint, 0) + 1
        return compteur

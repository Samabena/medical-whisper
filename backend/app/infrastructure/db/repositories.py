"""Implémentations SQLAlchemy des ports de repository (DATA-1.3 / DATA-1.4).

Chaque repo reçoit une `AsyncSession` (unité de travail par requête). Les méthodes
renvoient des **entités du domaine**, jamais des objets ORM.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.domain.entities import (
    Account,
    ApiKey,
    FormDefinition,
    LiveSession,
    UsageRecord,
)
from app.infrastructure.db import mappers as m
from app.infrastructure.db.models import (
    AccountORM,
    ApiKeyORM,
    FormDefinitionORM,
    LiveSessionORM,
    UsageRecordORM,
)
from sqlalchemy.ext.asyncio import AsyncSession


class SqlAccountRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, account: Account) -> Account:
        orm = m.apply_account(AccountORM(), account)
        self._s.add(orm)
        await self._s.commit()
        await self._s.refresh(orm)
        return m.account_to_domain(orm)

    async def get(self, account_id: int) -> Account | None:
        orm = await self._s.get(AccountORM, account_id)
        return m.account_to_domain(orm) if orm else None

    async def get_by_email(self, email: str) -> Account | None:
        res = await self._s.execute(
            select(AccountORM).where(AccountORM.email_contact == email)
        )
        orm = res.scalar_one_or_none()
        return m.account_to_domain(orm) if orm else None

    async def list(self) -> list[Account]:
        res = await self._s.execute(select(AccountORM).order_by(AccountORM.id))
        return [m.account_to_domain(o) for o in res.scalars().all()]

    async def update(self, account: Account) -> Account:
        orm = await self._s.get(AccountORM, account.id)
        if orm is None:
            raise ValueError(f"Compte {account.id} introuvable.")
        m.apply_account(orm, account)
        await self._s.commit()
        await self._s.refresh(orm)
        return m.account_to_domain(orm)


class SqlApiKeyRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, key: ApiKey) -> ApiKey:
        orm = ApiKeyORM(
            account_id=key.account_id,
            label=key.label,
            key_prefix=key.key_prefix,
            key_hash=key.key_hash,
            actif=key.actif,
            cree_a=key.cree_a,
        )
        self._s.add(orm)
        await self._s.commit()
        await self._s.refresh(orm)
        return m.apikey_to_domain(orm)

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        res = await self._s.execute(select(ApiKeyORM).where(ApiKeyORM.key_hash == key_hash))
        orm = res.scalar_one_or_none()
        return m.apikey_to_domain(orm) if orm else None

    async def list_for_account(self, account_id: int) -> list[ApiKey]:
        res = await self._s.execute(
            select(ApiKeyORM).where(ApiKeyORM.account_id == account_id).order_by(ApiKeyORM.id)
        )
        return [m.apikey_to_domain(o) for o in res.scalars().all()]

    async def revoke(self, key_id: int) -> ApiKey | None:
        orm = await self._s.get(ApiKeyORM, key_id)
        if orm is None:
            return None
        orm.actif = False
        await self._s.commit()
        await self._s.refresh(orm)
        return m.apikey_to_domain(orm)


class SqlFormRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, form: FormDefinition) -> FormDefinition:
        orm = m.apply_form(FormDefinitionORM(), form)
        self._s.add(orm)
        await self._s.commit()
        await self._s.refresh(orm)
        return m.form_to_domain(orm)

    async def get(self, account_id: int, form_id: str) -> FormDefinition | None:
        res = await self._s.execute(
            select(FormDefinitionORM)
            .where(
                FormDefinitionORM.account_id == account_id,
                FormDefinitionORM.form_id == form_id,
            )
            .order_by(FormDefinitionORM.version.desc())
        )
        orm = res.scalars().first()
        return m.form_to_domain(orm) if orm else None

    async def list_for_account(self, account_id: int) -> list[FormDefinition]:
        res = await self._s.execute(
            select(FormDefinitionORM)
            .where(FormDefinitionORM.account_id == account_id)
            .order_by(FormDefinitionORM.id)
        )
        return [m.form_to_domain(o) for o in res.scalars().all()]

    async def update(self, form: FormDefinition) -> FormDefinition:
        orm = await self._s.get(FormDefinitionORM, form.id)
        if orm is None:
            raise ValueError(f"Formulaire {form.id} introuvable.")
        m.apply_form(orm, form)
        await self._s.commit()
        await self._s.refresh(orm)
        return m.form_to_domain(orm)


class SqlSessionRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, session: LiveSession) -> LiveSession:
        orm = LiveSessionORM(
            id=session.id,
            account_id=session.account_id,
            form_id=session.form_id,
            statut=session.statut.value,
            cree_a=session.cree_a,
            expires_at=session.expires_at,
        )
        self._s.add(orm)
        await self._s.commit()
        return session

    async def get(self, session_id: str) -> LiveSession | None:
        orm = await self._s.get(LiveSessionORM, session_id)
        return m.session_to_domain(orm) if orm else None

    async def update(self, session: LiveSession) -> LiveSession:
        orm = await self._s.get(LiveSessionORM, session.id)
        if orm is None:
            raise ValueError(f"Session {session.id} introuvable.")
        orm.statut = session.statut.value
        orm.expires_at = session.expires_at
        await self._s.commit()
        return session


class SqlUsageRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record(self, usage: UsageRecord) -> UsageRecord:
        orm = UsageRecordORM(
            account_id=usage.account_id, endpoint=usage.endpoint, horodatage=usage.horodatage
        )
        self._s.add(orm)
        await self._s.commit()
        await self._s.refresh(orm)
        return m.usage_to_domain(orm)

    async def count_by_endpoint(self, account_id: int) -> dict[str, int]:
        res = await self._s.execute(
            select(UsageRecordORM.endpoint, func.count())
            .where(UsageRecordORM.account_id == account_id)
            .group_by(UsageRecordORM.endpoint)
        )
        return {endpoint: total for endpoint, total in res.all()}

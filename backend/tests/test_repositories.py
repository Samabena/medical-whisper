"""DATA-1.3 — les repositories SQLAlchemy honorent le contrat des ports (sur aiosqlite)."""

from __future__ import annotations

import pytest

from app.domain.entities import Account, ApiKey, FormDefinition, FormField, UsageRecord
from app.domain.value_objects import FieldType, FormStatus, Language
from app.infrastructure.db.repositories import (
    SqlAccountRepo,
    SqlApiKeyRepo,
    SqlFormRepo,
    SqlUsageRepo,
)


async def test_account_crud(db_session):
    repo = SqlAccountRepo(db_session)
    cree = await repo.add(Account(nom="Clinique A", email_contact="a@ex.com", langue=Language.EN))
    assert cree.id is not None
    assert cree.langue is Language.EN

    assert (await repo.get(cree.id)).email_contact == "a@ex.com"
    assert (await repo.get_by_email("a@ex.com")).id == cree.id

    cree.actif = False
    maj = await repo.update(cree)
    assert maj.actif is False
    assert len(await repo.list()) == 1


async def test_apikey_rotation_et_revocation(db_session):
    accounts = SqlAccountRepo(db_session)
    keys = SqlApiKeyRepo(db_session)
    compte = await accounts.add(Account(nom="C", email_contact="c@ex.com"))

    k1 = await keys.add(ApiKey(account_id=compte.id, key_prefix="aaaaaaaa", key_hash="h1"))
    k2 = await keys.add(ApiKey(account_id=compte.id, key_prefix="bbbbbbbb", key_hash="h2"))

    # Rotation : deux clés actives en parallèle, toutes deux résolvables par leur hash.
    assert (await keys.get_by_hash("h1")).id == k1.id
    assert (await keys.get_by_hash("h2")).id == k2.id
    assert len(await keys.list_for_account(compte.id)) == 2

    # Révocation immédiate de k1.
    revoquee = await keys.revoke(k1.id)
    assert revoquee.actif is False
    assert (await keys.get_by_hash("h1")).actif is False
    assert (await keys.get_by_hash("h2")).actif is True


async def test_form_versionne_et_scope_compte(db_session):
    accounts = SqlAccountRepo(db_session)
    forms = SqlFormRepo(db_session)
    a1 = await accounts.add(Account(nom="A1", email_contact="a1@ex.com"))
    a2 = await accounts.add(Account(nom="A2", email_contact="a2@ex.com"))

    await forms.add(
        FormDefinition(
            account_id=a1.id,
            form_id="consultation",
            titre="Consultation",
            version=1,
            fields=[
                FormField("nom", "Nom", FieldType.STRING, required=True),
                FormField("sexe", "Sexe", FieldType.ENUM, enum_values=["m", "f"]),
            ],
        )
    )
    await forms.add(
        FormDefinition(
            account_id=a1.id, form_id="consultation", titre="Consultation v2",
            version=2, statut=FormStatus.PUBLISHED,
        )
    )

    # get renvoie la dernière version, scopée au compte.
    dernier = await forms.get(a1.id, "consultation")
    assert dernier.version == 2 and dernier.statut is FormStatus.PUBLISHED
    # Isolation : a2 ne voit pas le formulaire de a1.
    assert await forms.get(a2.id, "consultation") is None
    # Les champs (JSON) sont reconstitués en entités.
    v1 = next(f for f in await forms.list_for_account(a1.id) if f.version == 1)
    assert v1.fields[1].type is FieldType.ENUM and v1.fields[1].enum_values == ["m", "f"]


async def test_usage_compte_par_endpoint(db_session):
    accounts = SqlAccountRepo(db_session)
    usage = SqlUsageRepo(db_session)
    compte = await accounts.add(Account(nom="U", email_contact="u@ex.com"))

    for endpoint in ("session_create", "session_create", "session_reply"):
        await usage.record(UsageRecord(account_id=compte.id, endpoint=endpoint))

    counts = await usage.count_by_endpoint(compte.id)
    assert counts == {"session_create": 2, "session_reply": 1}

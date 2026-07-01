"""INT-5.1 — cas d'usage StartLiveSession (langue effective, formulaire inconnu)."""

from __future__ import annotations

import pytest

from app.application.integration.start_session import StartLiveSession
from app.domain.entities import Account, FormDefinition, FormField
from app.domain.errors import NotFoundError
from app.domain.value_objects import FieldType, Language
from app.infrastructure.security.jwt_tokens import JwtTokenService
from tests.fakes import InMemoryFormRepo, InMemorySessionRepo


async def test_demarrage_ok_langue_du_formulaire_prioritaire():
    forms, sessions = InMemoryFormRepo(), InMemorySessionRepo()
    account = Account(nom="A", email_contact="a@ex.com", langue=Language.EN, id=1)
    await forms.add(
        FormDefinition(
            account_id=1,
            form_id="f",
            titre="F",
            langue=Language.FR,  # surcharge la langue EN du compte
            fields=[FormField("nom", "Nom", FieldType.STRING, required=True)],
        )
    )
    uc = StartLiveSession(forms, sessions, JwtTokenService("s"), ttl_seconds=60)
    res = await uc.execute(account, "f")

    assert res.language == "fr"
    assert res.token
    assert res.form_schema["fields"][0]["required"] is True
    persistee = await sessions.get(res.session_id)
    assert persistee is not None and persistee.account_id == 1


async def test_formulaire_inconnu_404():
    forms, sessions = InMemoryFormRepo(), InMemorySessionRepo()
    account = Account(nom="A", email_contact="a@ex.com", id=1)
    uc = StartLiveSession(forms, sessions, JwtTokenService("s"), ttl_seconds=60)
    with pytest.raises(NotFoundError):
        await uc.execute(account, "absent")

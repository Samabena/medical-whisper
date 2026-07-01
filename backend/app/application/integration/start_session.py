"""Démarrage d'une session live (INT-5.1).

Vérifie que le formulaire appartient au compte, crée la session (statut `pending` + TTL),
puis émet un jeton éphémère. La langue effective = langue du formulaire sinon du compte.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.application.forms.schema import form_schema
from app.application.ports.repositories import FormRepo, SessionRepo
from app.application.ports.token_service import EphemeralTokenPort
from app.domain.entities import Account, LiveSession
from app.domain.errors import NotFoundError
from app.domain.value_objects import SessionStatus


@dataclass(frozen=True)
class StartLiveSessionResult:
    session_id: str
    token: str
    expires_at: datetime
    language: str
    form_schema: dict


class StartLiveSession:
    def __init__(
        self,
        forms: FormRepo,
        sessions: SessionRepo,
        tokens: EphemeralTokenPort,
        ttl_seconds: int,
    ) -> None:
        self._forms = forms
        self._sessions = sessions
        self._tokens = tokens
        self._ttl = ttl_seconds

    async def execute(self, account: Account, form_id: str) -> StartLiveSessionResult:
        form = await self._forms.get(account.id, form_id)
        if form is None:
            raise NotFoundError(f"Formulaire {form_id!r} introuvable pour ce compte.")

        expires_at = datetime.now(tz=timezone.utc) + timedelta(seconds=self._ttl)
        session = LiveSession(
            account_id=account.id,
            form_id=form_id,
            statut=SessionStatus.PENDING,
            expires_at=expires_at,
        )
        await self._sessions.add(session)

        jeton = self._tokens.mint(session.id, self._ttl)
        langue = (form.langue or account.langue).value
        return StartLiveSessionResult(
            session_id=session.id,
            token=jeton.token,
            expires_at=jeton.expires_at,
            language=langue,
            form_schema=form_schema(form),
        )

"""Stockage en mémoire des sessions de formulaire."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from app.config import get_settings


@dataclass
class Session:
    session_id: str
    form_id: str
    formulaire_partiel: dict
    statut: str = "clarification"
    champ_en_attente: str | None = None
    # Compteur de relances par champ + champs abandonnés (garde-fou anti-boucle :
    # un champ que le LLM n'arrive pas à extraire ne doit pas être redemandé sans fin).
    tentatives: dict[str, int] = field(default_factory=dict)
    champs_abandonnes: list[str] = field(default_factory=list)
    cree_le: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    mis_a_jour_le: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


_sessions: dict[str, Session] = {}


def creer_session(form_id: str, formulaire: BaseModel, champ_en_attente: str | None) -> Session:
    session_id = str(uuid.uuid4())
    session = Session(
        session_id=session_id,
        form_id=form_id,
        formulaire_partiel=formulaire.model_dump(),
        champ_en_attente=champ_en_attente,
    )
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> Session | None:
    session = _sessions.get(session_id)
    if session is None:
        return None
    settings = get_settings()
    ttl = timedelta(minutes=settings.session_ttl_minutes)
    if datetime.now(tz=timezone.utc) - session.mis_a_jour_le > ttl:
        del _sessions[session_id]
        return None
    return session


def mettre_a_jour_session(session_id: str, formulaire: BaseModel, champ_en_attente: str | None) -> Session | None:
    session = _sessions.get(session_id)
    if session is None:
        return None
    session.formulaire_partiel = formulaire.model_dump()
    session.champ_en_attente = champ_en_attente
    session.mis_a_jour_le = datetime.now(tz=timezone.utc)
    return session


def fermer_session(session_id: str) -> None:
    _sessions.pop(session_id, None)


def vider_sessions() -> None:
    _sessions.clear()

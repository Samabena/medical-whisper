"""Schémas des réponses API (indépendants des formulaires)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReponseTermine(BaseModel):
    """Réponse quand le formulaire est complet."""

    statut: str = "termine"
    formulaire: dict = Field(default_factory=dict)
    transcription: str = ""  # texte transcrit du dernier audio (vide si pas d'audio)


class ReponseClarification(BaseModel):
    """Réponse quand une clarification est nécessaire."""

    statut: str = "clarification"
    session_id: str
    question_texte: str
    question_audio: str  # base64 WAV
    champs_restants: list[str]
    transcription: str = ""  # texte transcrit du dernier audio


class EtatSession(BaseModel):
    """État courant d'une session de remplissage."""

    session_id: str
    statut: str
    form_id: str
    formulaire_partiel: dict
    champ_en_attente: str | None
    champs_restants: list[str]

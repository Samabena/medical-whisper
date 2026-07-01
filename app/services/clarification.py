"""Service de clarification — détecte les champs manquants et génère des questions."""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

from pydantic import BaseModel

from app.services.tts import synthetiser  # noqa: F401 — importé pour être mockable

logger = logging.getLogger(__name__)

_QUESTIONS: dict[str, str] = {
    "nom_patient": "Quel est le nom du patient ?",
    "prenom_patient": "Quel est le prénom du patient ?",
    "date_naissance": "Quelle est la date de naissance du patient ?",
    "date_consultation": "Quelle est la date de la consultation ?",
    "motif": "Quel est le motif de la consultation ?",
    "diagnostic": "Quel est le diagnostic ?",
    "date_intervention": "Quelle est la date de l'intervention chirurgicale ?",
    "type_intervention": "Quel est le type d'intervention réalisé ?",
    "chirurgien": "Quel est le nom du chirurgien ?",
    "type_anesthesie": "Quel type d'anesthésie a été utilisé ?",
    "saignement": "Quel était le niveau de saignement ?",
    "sexe": "Quel est le sexe du patient ?",
    "medecin_traitant": "Quel est le médecin traitant ?",
    "duree_minutes": "Quelle a été la durée de l'intervention en minutes ?",
}


@dataclass
class ChampAClarifier:
    nom: str
    raison: str  # "manquant" ou "incertain"


def analyser(formulaire: BaseModel) -> list[ChampAClarifier]:
    """Retourne les champs à clarifier : obligatoires manquants d'abord, puis incertains."""
    champs_obligatoires: frozenset[str] = getattr(
        type(formulaire), "CHAMPS_OBLIGATOIRES", frozenset()
    )
    donnees = formulaire.model_dump()

    manquants: list[ChampAClarifier] = []
    incertains: list[ChampAClarifier] = []

    for nom_champ, valeur_brute in donnees.items():
        if not isinstance(valeur_brute, dict):
            continue
        valeur = valeur_brute.get("valeur")
        confiance = valeur_brute.get("confiance", "manquant")

        if valeur is None or confiance == "manquant":
            if nom_champ in champs_obligatoires:
                manquants.append(ChampAClarifier(nom=nom_champ, raison="manquant"))
        elif confiance == "incertain":
            incertains.append(ChampAClarifier(nom=nom_champ, raison="incertain"))

    return manquants + incertains


def formuler_question_texte(champ: ChampAClarifier) -> str:
    """Retourne la question associée au champ (gabarit ou générique)."""
    if champ.nom in _QUESTIONS:
        return _QUESTIONS[champ.nom]
    label = champ.nom.replace("_", " ")
    return f"Pouvez-vous préciser le champ «{champ.nom}» ({label}) ?"


def generer_question_audio(formulaire: BaseModel) -> tuple[str, bytes]:
    """Génère la question audio pour le premier champ à clarifier.

    Returns (question_texte, wav_bytes).
    Raises ValueError si le formulaire est complet.
    """
    champs = analyser(formulaire)
    if not champs:
        raise ValueError("Le formulaire est complet — aucune clarification nécessaire.")
    premier = champs[0]
    texte = formuler_question_texte(premier)
    wav_bytes = synthetiser(texte)
    return texte, wav_bytes

"""Routes de gestion des sessions de remplissage vocal."""

from __future__ import annotations

import base64
import logging
import os
import tempfile

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.catalog.forms_catalog import get_form_model
from app.schemas.api import EtatSession, ReponseClarification, ReponseTermine
from app.services.clarification import analyser, generer_question_audio
from app.services.extraction import ExtractionError, extraire
from app.services.stt import STTError, transcrire
from app.sessions.store import creer_session, fermer_session, get_session, mettre_a_jour_session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Sessions"])

# Nombre de relances vocales sur un même champ avant de l'abandonner (garde-fou
# anti-boucle : sans cette limite, un champ que le LLM n'extrait jamais ferait
# boucler la session indéfiniment).
MAX_TENTATIVES_PAR_CHAMP = 3


async def _transcrire_upload(audio: UploadFile) -> str:
    audio_bytes = await audio.read()
    suffix = os.path.splitext(audio.filename or ".wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        return transcrire(tmp_path)
    except STTError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _extraire_ou_503(texte, form_id, formulaire_partiel=None):
    """Extraction LLM avec échec géré : toute erreur → 503 service_indisponible."""
    try:
        return extraire(texte, form_id, formulaire_partiel)
    except ExtractionError as exc:
        logger.warning("Extraction indisponible : %s", exc)
        raise HTTPException(status_code=503, detail=f"Extraction indisponible : {exc}")
    except Exception as exc:  # filet de sécurité : on ne laisse jamais filer un 500
        logger.exception("Erreur inattendue d'extraction")
        raise HTTPException(status_code=503, detail=f"Extraction indisponible : {exc}")


def _question_audio_ou_503(formulaire):
    """Génération de la question audio (TTS) avec échec géré → 503."""
    try:
        return generer_question_audio(formulaire)
    except Exception as exc:
        logger.exception("Erreur de synthèse vocale (TTS)")
        raise HTTPException(status_code=503, detail=f"Synthèse vocale indisponible : {exc}")


@router.post("/sessions")
async def creer_nouvelle_session(
    form_id: str = Form(...),
    audio: UploadFile = None,
) -> JSONResponse:
    """Crée une session et traite la première réponse audio."""
    try:
        form_model = get_form_model(form_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    formulaire = form_model()

    texte = ""
    if audio is not None:
        texte = await _transcrire_upload(audio)
        logger.info("Session nouvelle — transcription : %r", texte[:80])
        formulaire = _extraire_ou_503(texte, form_id)

    champs_manquants = analyser(formulaire)

    if not champs_manquants:
        return JSONResponse(
            content=ReponseTermine(
                formulaire=formulaire.model_dump(), transcription=texte
            ).model_dump()
        )

    premier_champ = champs_manquants[0]
    session = creer_session(form_id, formulaire, premier_champ.nom)

    question_texte, wav_bytes = _question_audio_ou_503(formulaire)
    question_audio = base64.b64encode(wav_bytes).decode("utf-8")

    return JSONResponse(
        content=ReponseClarification(
            statut="clarification",
            session_id=session.session_id,
            question_texte=question_texte,
            question_audio=question_audio,
            champs_restants=[c.nom for c in champs_manquants],
            transcription=texte,
        ).model_dump()
    )


@router.post("/sessions/{session_id}/repondre")
async def repondre_session(session_id: str, audio: UploadFile) -> JSONResponse:
    """Soumet une réponse audio pour continuer le remplissage."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} introuvable ou expirée.")

    texte = await _transcrire_upload(audio)
    logger.info("Session %s — transcription : %r", session_id, texte[:80])

    form_model = get_form_model(session.form_id)
    formulaire_partiel = form_model.model_validate(session.formulaire_partiel)
    formulaire = _extraire_ou_503(texte, session.form_id, formulaire_partiel)

    # Garde-fou anti-boucle : on compte la relance sur le champ qui était demandé.
    # S'il reste vide après MAX_TENTATIVES_PAR_CHAMP, on l'abandonne (le LLM n'arrive
    # pas à l'extraire) — il restera "manquant" pour la vérification humaine ultérieure.
    champ_demande = session.champ_en_attente
    if champ_demande:
        session.tentatives[champ_demande] = session.tentatives.get(champ_demande, 0) + 1

    abandonnes = set(session.champs_abandonnes)
    for champ in analyser(formulaire):
        if session.tentatives.get(champ.nom, 0) >= MAX_TENTATIVES_PAR_CHAMP:
            abandonnes.add(champ.nom)
    session.champs_abandonnes = sorted(abandonnes)

    # Champs encore à clarifier = manquants non abandonnés.
    a_clarifier = [c for c in analyser(formulaire) if c.nom not in abandonnes]

    if not a_clarifier:
        # Plus rien à demander (formulaire complet, ou champs restants abandonnés).
        # On termine : les éventuels champs non remplis sont laissés "manquant".
        if abandonnes:
            logger.info("Session %s terminée avec champs abandonnés : %s", session_id, session.champs_abandonnes)
        fermer_session(session_id)
        return JSONResponse(
            content=ReponseTermine(
                formulaire=formulaire.model_dump(), transcription=texte
            ).model_dump()
        )

    prochain_champ = a_clarifier[0]
    mettre_a_jour_session(session_id, formulaire, prochain_champ.nom)

    question_texte, wav_bytes = _question_audio_ou_503(formulaire)
    question_audio = base64.b64encode(wav_bytes).decode("utf-8")

    return JSONResponse(
        content=ReponseClarification(
            statut="clarification",
            session_id=session_id,
            question_texte=question_texte,
            question_audio=question_audio,
            champs_restants=[c.nom for c in a_clarifier],
            transcription=texte,
        ).model_dump()
    )


@router.get("/sessions/{session_id}")
def etat_session(session_id: str) -> EtatSession:
    """Retourne l'état courant d'une session."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} introuvable ou expirée.")

    form_model = get_form_model(session.form_id)
    formulaire = form_model.model_validate(session.formulaire_partiel)
    champs_manquants = analyser(formulaire)

    return EtatSession(
        session_id=session_id,
        statut=session.statut,
        form_id=session.form_id,
        formulaire_partiel=session.formulaire_partiel,
        champ_en_attente=session.champ_en_attente,
        champs_restants=[c.nom for c in champs_manquants],
    )

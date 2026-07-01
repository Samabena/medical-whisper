"""Opérations CRUD pour le portail admin."""

from __future__ import annotations

import hashlib
import secrets

from sqlalchemy.orm import Session

from app.admin.models import CleAPI, ClientCompte, UsageLog


def _hacher(cle: str) -> str:
    return hashlib.sha256(cle.encode()).hexdigest()


def _masquer(cle_hachee: str) -> str:
    return cle_hachee[:6] + "..." + cle_hachee[-4:]


def creer_compte(db: Session, nom: str, email_contact: str) -> ClientCompte:
    compte = ClientCompte(nom=nom, email_contact=email_contact)
    db.add(compte)
    db.commit()
    db.refresh(compte)
    return compte


def lister_comptes(db: Session) -> list[ClientCompte]:
    return db.query(ClientCompte).all()


def get_compte(db: Session, compte_id: int) -> ClientCompte | None:
    return db.query(ClientCompte).filter(ClientCompte.id == compte_id).first()


def desactiver_compte(db: Session, compte_id: int) -> ClientCompte | None:
    compte = get_compte(db, compte_id)
    if compte:
        compte.actif = False
        db.commit()
        db.refresh(compte)
    return compte


def creer_cle(db: Session, compte_id: int, label: str = "Clé principale") -> tuple[str, CleAPI]:
    """Génère une clé API, la stocke hachée et retourne la clé en clair."""
    cle_claire = secrets.token_urlsafe(32)
    cle_hachee = _hacher(cle_claire)
    cle = CleAPI(compte_id=compte_id, label=label, cle_hachee=cle_hachee)
    db.add(cle)
    db.commit()
    db.refresh(cle)
    return cle_claire, cle


def creer_cle_depuis_claire(db: Session, compte_id: int, cle_claire: str, label: str = "Importée") -> CleAPI:
    """Importe une clé existante (depuis la config) en la hachant."""
    cle_hachee = _hacher(cle_claire)
    existante = db.query(CleAPI).filter(CleAPI.cle_hachee == cle_hachee).first()
    if existante:
        return existante
    cle = CleAPI(compte_id=compte_id, label=label, cle_hachee=cle_hachee)
    db.add(cle)
    db.commit()
    db.refresh(cle)
    return cle


def lister_cles(db: Session, compte_id: int) -> list[CleAPI]:
    return db.query(CleAPI).filter(CleAPI.compte_id == compte_id).all()


def revoquer_cle(db: Session, cle_id: int) -> CleAPI | None:
    cle = db.query(CleAPI).filter(CleAPI.id == cle_id).first()
    if cle:
        cle.actif = False
        db.commit()
        db.refresh(cle)
    return cle


def verifier_cle_api_db(db: Session, cle_claire: str | None) -> ClientCompte | None:
    """Vérifie la clé API et retourne le compte associé si valide."""
    if not cle_claire:
        return None
    cle_hachee = _hacher(cle_claire)
    cle = (
        db.query(CleAPI)
        .filter(CleAPI.cle_hachee == cle_hachee, CleAPI.actif == True)  # noqa: E712
        .first()
    )
    if cle is None:
        return None
    compte = get_compte(db, cle.compte_id)
    return compte if compte and compte.actif else None


def enregistrer_usage(db: Session, compte_id: int, endpoint: str, avec_tokens: bool = False) -> UsageLog:
    log = UsageLog(compte_id=compte_id, endpoint=endpoint, tokens=1 if avec_tokens else 0)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def stats_usage_compte(db: Session, compte_id: int) -> dict:
    logs = db.query(UsageLog).filter(UsageLog.compte_id == compte_id).all()
    total_sessions = sum(1 for l in logs if l.endpoint == "session_create")
    total_clarifications = sum(1 for l in logs if l.endpoint == "session_reply")
    return {
        "compte_id": compte_id,
        "total_sessions": total_sessions,
        "total_clarifications": total_clarifications,
    }


def stats_globales(db: Session) -> dict:
    nb_comptes = db.query(ClientCompte).count()
    nb_cles_actives = db.query(CleAPI).filter(CleAPI.actif == True).count()  # noqa: E712
    nb_appels = db.query(UsageLog).count()
    return {"nb_comptes": nb_comptes, "nb_cles_actives": nb_cles_actives, "nb_appels": nb_appels}

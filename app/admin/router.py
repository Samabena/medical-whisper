"""Routeurs du portail admin — API REST + interface web."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.admin.crud import (
    creer_cle,
    creer_compte,
    desactiver_compte,
    get_compte,
    lister_cles,
    lister_comptes,
    revoquer_cle,
    stats_globales,
    stats_usage_compte,
    _masquer,
)
from app.admin.database import get_db
from app.catalog.forms_catalog import get_form_ids, get_form_label, get_form_model

_templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
templates = Jinja2Templates(directory=_templates_dir)


def _format_horodatage(ts) -> str:
    """Filtre Jinja : convertit un timestamp epoch en date lisible (fr)."""
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError, OSError):
        return str(ts)


templates.env.filters["dt"] = _format_horodatage

# --- API REST (visible dans Swagger) ---
api_router = APIRouter(prefix="/admin/api", tags=["Admin API"])


class CompteCreate(BaseModel):
    nom: str
    email_contact: str


class CleCreate(BaseModel):
    label: str = "Clé principale"


class CompteOut(BaseModel):
    id: int
    nom: str
    email_contact: str
    actif: bool
    date_creation: int


class CleOut(BaseModel):
    id: int
    label: str
    actif: bool
    cree_a: int
    cle_masquee: str


class CleCreeOut(BaseModel):
    id: int
    label: str
    cle_en_clair: str
    actif: bool
    cree_a: int


class CleRevoqueeOut(BaseModel):
    id: int
    actif: bool


class UsageOut(BaseModel):
    compte_id: int
    total_sessions: int
    total_clarifications: int


class StatsOut(BaseModel):
    nb_comptes: int
    nb_cles_actives: int
    nb_appels: int


def _compte_dict(c) -> dict:
    return {
        "id": c.id,
        "nom": c.nom,
        "email_contact": c.email_contact,
        "actif": c.actif,
        "date_creation": c.date_creation,
    }


@api_router.get("/comptes", response_model=list[CompteOut])
def api_lister_comptes(db: Session = Depends(get_db)):
    return [_compte_dict(c) for c in lister_comptes(db)]


@api_router.post("/comptes", status_code=201, response_model=CompteOut)
def api_creer_compte(body: CompteCreate, db: Session = Depends(get_db)):
    compte = creer_compte(db, body.nom, body.email_contact)
    return _compte_dict(compte)


@api_router.get("/comptes/{compte_id}", response_model=CompteOut)
def api_get_compte(compte_id: str, db: Session = Depends(get_db)):
    try:
        cid = int(compte_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Compte introuvable.")
    compte = get_compte(db, cid)
    if compte is None:
        raise HTTPException(status_code=404, detail="Compte introuvable.")
    return _compte_dict(compte)


@api_router.patch("/comptes/{compte_id}/desactiver", response_model=CompteOut)
def api_desactiver_compte(compte_id: int, db: Session = Depends(get_db)):
    compte = desactiver_compte(db, compte_id)
    if compte is None:
        raise HTTPException(status_code=404, detail="Compte introuvable.")
    return _compte_dict(compte)


@api_router.get("/comptes/{compte_id}/cles", response_model=list[CleOut])
def api_lister_cles(compte_id: int, db: Session = Depends(get_db)):
    cles = lister_cles(db, compte_id)
    return [
        {
            "id": c.id,
            "label": c.label,
            "actif": c.actif,
            "cree_a": c.cree_a,
            "cle_masquee": _masquer(c.cle_hachee),
        }
        for c in cles
    ]


@api_router.post("/comptes/{compte_id}/cles", status_code=201, response_model=CleCreeOut)
def api_creer_cle(compte_id: int, body: CleCreate = CleCreate(), db: Session = Depends(get_db)):
    cle_claire, cle = creer_cle(db, compte_id, body.label)
    return {
        "id": cle.id,
        "label": cle.label,
        "cle_en_clair": cle_claire,
        "actif": cle.actif,
        "cree_a": cle.cree_a,
    }


@api_router.delete("/comptes/{compte_id}/cles/{cle_id}", response_model=CleRevoqueeOut)
def api_revoquer_cle(compte_id: int, cle_id: int, db: Session = Depends(get_db)):
    cle = revoquer_cle(db, cle_id)
    if cle is None:
        raise HTTPException(status_code=404, detail="Clé introuvable.")
    return {"id": cle.id, "actif": cle.actif}


@api_router.get("/usage", response_model=list[UsageOut])
def api_usage(compte_id: int, db: Session = Depends(get_db)):
    return [stats_usage_compte(db, compte_id)]


@api_router.get("/stats", response_model=StatsOut)
def api_stats(db: Session = Depends(get_db)):
    return stats_globales(db)


# --- Interface Web (exclue du Swagger) ---
ui_router = APIRouter(prefix="/admin", include_in_schema=False)


def _est_connecte(request: Request) -> bool:
    return request.session.get("admin_connecte") is True


@ui_router.get("/connexion", response_class=HTMLResponse)
def page_connexion(request: Request):
    return templates.TemplateResponse(request, "admin/login.html", {})


@ui_router.post("/connexion")
async def traiter_connexion(
    request: Request,
    mot_de_passe: Annotated[str, Form()] = "",
):
    from app.config import get_settings
    settings = get_settings()
    if secrets.compare_digest(mot_de_passe, settings.admin_password):
        request.session["admin_connecte"] = True
        return RedirectResponse(url="/admin/", status_code=302)
    return templates.TemplateResponse(
        request,
        "admin/login.html",
        {"erreur": "Mot de passe incorrect."},
        status_code=401,
    )


@ui_router.get("/deconnexion")
def deconnecter(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/connexion", status_code=302)


@ui_router.get("/", response_class=HTMLResponse)
def page_dashboard(request: Request, db: Session = Depends(get_db)):
    if not _est_connecte(request):
        return RedirectResponse(url="/admin/connexion", status_code=302)
    comptes = lister_comptes(db)
    stats = stats_globales(db)
    return templates.TemplateResponse(
        request, "admin/dashboard.html", {"comptes": comptes, "stats": stats}
    )


@ui_router.post("/comptes")
def ui_creer_compte(
    request: Request,
    nom: Annotated[str, Form()],
    email_contact: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    if not _est_connecte(request):
        return RedirectResponse(url="/admin/connexion", status_code=302)
    creer_compte(db, nom, email_contact)
    return RedirectResponse(url="/admin/", status_code=302)


@ui_router.get("/comptes/{compte_id}/cles", response_class=HTMLResponse)
def page_cles(request: Request, compte_id: int, db: Session = Depends(get_db)):
    if not _est_connecte(request):
        return RedirectResponse(url="/admin/connexion", status_code=302)
    cles = lister_cles(db, compte_id)
    return templates.TemplateResponse(
        request, "admin/keys.html", {"compte_id": compte_id, "cles": cles}
    )


@ui_router.post("/comptes/{compte_id}/cles", response_class=HTMLResponse)
def ui_creer_cle(request: Request, compte_id: int, db: Session = Depends(get_db)):
    if not _est_connecte(request):
        return RedirectResponse(url="/admin/connexion", status_code=302)
    cle_claire, cle = creer_cle(db, compte_id)
    cles = lister_cles(db, compte_id)
    return templates.TemplateResponse(
        request,
        "admin/keys.html",
        {"compte_id": compte_id, "cles": cles, "nouvelle_cle": cle_claire},
    )


@ui_router.post("/comptes/{compte_id}/cles/{cle_id}/revoquer")
def ui_revoquer_cle(request: Request, compte_id: int, cle_id: int, db: Session = Depends(get_db)):
    if not _est_connecte(request):
        return RedirectResponse(url="/admin/connexion", status_code=302)
    revoquer_cle(db, cle_id)
    return RedirectResponse(url=f"/admin/comptes/{compte_id}/cles", status_code=302)


@ui_router.get("/formulaires", response_class=HTMLResponse)
def page_formulaires(request: Request):
    if not _est_connecte(request):
        return RedirectResponse(url="/admin/connexion", status_code=302)
    forms = [{"id": fid, "label": get_form_label(fid)} for fid in get_form_ids()]
    return templates.TemplateResponse(request, "admin/forms.html", {"forms": forms})


@ui_router.get("/formulaires/{form_id}/schema")
def page_schema_formulaire(request: Request, form_id: str):
    if not _est_connecte(request):
        return RedirectResponse(url="/admin/connexion", status_code=302)
    try:
        model = get_form_model(form_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Formulaire inconnu.")
    return JSONResponse(model.model_json_schema())

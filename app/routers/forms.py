"""Routes de découverte des formulaires disponibles."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.catalog.forms_catalog import get_form_ids, get_form_model

router = APIRouter(tags=["Formulaires"])


@router.get("/forms")
def lister_formulaires() -> list[str]:
    """Liste les identifiants de tous les formulaires disponibles."""
    return get_form_ids()


@router.get("/forms/{form_id}")
def obtenir_formulaire(form_id: str) -> dict:
    """Retourne le schéma JSON d'un formulaire."""
    try:
        model = get_form_model(form_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return model.model_json_schema()

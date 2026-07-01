"""API admin — constructeur de formulaires dynamiques (FORM-4.1). Protégé par require_admin."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.application.admin.forms import (
    CreateForm,
    GetForm,
    ListForms,
    PublishForm,
    UpdateForm,
)
from app.application.forms.schema import form_schema
from app.application.ports.repositories import FormRepo
from app.domain.entities import FormDefinition, FormField
from app.domain.value_objects import FieldType, FormStatus, Language
from app.interface import deps

router = APIRouter(
    prefix="/admin/api", tags=["Admin · Formulaires"], dependencies=[Depends(deps.require_admin)]
)


class FieldIn(BaseModel):
    name: str
    label: str
    type: FieldType
    required: bool = False
    enum_values: list[str] = []
    description: str = ""


class FormCreate(BaseModel):
    form_id: str
    titre: str
    langue: Language | None = None
    fields: list[FieldIn] = []


class FormUpdate(BaseModel):
    titre: str | None = None
    langue: Language | None = None
    fields: list[FieldIn] | None = None


class FormOut(BaseModel):
    id: int | None
    form_id: str
    titre: str
    version: int
    statut: FormStatus
    language: str | None
    fields: list[dict]


def _to_fields(fields: list[FieldIn]) -> list[FormField]:
    # FormField.__post_init__ valide (ex. enum sans valeurs → ValidationError → 422).
    return [
        FormField(
            name=f.name, label=f.label, type=f.type, required=f.required,
            enum_values=f.enum_values, description=f.description,
        )
        for f in fields
    ]


def _form_out(f: FormDefinition) -> FormOut:
    return FormOut(
        id=f.id, form_id=f.form_id, titre=f.titre, version=f.version, statut=f.statut,
        language=f.langue.value if f.langue else None, fields=form_schema(f)["fields"],
    )


@router.post("/accounts/{account_id}/forms", status_code=201, response_model=FormOut)
async def creer_formulaire(
    account_id: int, body: FormCreate, forms: FormRepo = Depends(deps.form_repo)
):
    form = await CreateForm(forms).execute(
        account_id, body.form_id, body.titre, _to_fields(body.fields), body.langue
    )
    return _form_out(form)


@router.get("/accounts/{account_id}/forms", response_model=list[FormOut])
async def lister_formulaires(account_id: int, forms: FormRepo = Depends(deps.form_repo)):
    return [_form_out(f) for f in await ListForms(forms).execute(account_id)]


@router.get("/accounts/{account_id}/forms/{form_id}", response_model=FormOut)
async def obtenir_formulaire(
    account_id: int, form_id: str, forms: FormRepo = Depends(deps.form_repo)
):
    return _form_out(await GetForm(forms).execute(account_id, form_id))


@router.patch("/accounts/{account_id}/forms/{form_id}", response_model=FormOut)
async def modifier_formulaire(
    account_id: int, form_id: str, body: FormUpdate, forms: FormRepo = Depends(deps.form_repo)
):
    form = await UpdateForm(forms).execute(
        account_id,
        form_id,
        titre=body.titre,
        fields=_to_fields(body.fields) if body.fields is not None else None,
        langue=body.langue,
    )
    return _form_out(form)


@router.post("/accounts/{account_id}/forms/{form_id}/publish", response_model=FormOut)
async def publier_formulaire(
    account_id: int, form_id: str, forms: FormRepo = Depends(deps.form_repo)
):
    return _form_out(await PublishForm(forms).execute(account_id, form_id))

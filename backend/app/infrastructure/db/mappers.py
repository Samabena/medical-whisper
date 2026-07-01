"""Conversion ORM ↔ entités du domaine (le domaine ignore SQLAlchemy)."""

from __future__ import annotations

from app.domain.entities import (
    Account,
    ApiKey,
    FormDefinition,
    FormField,
    LiveSession,
    UsageRecord,
)
from app.domain.value_objects import FieldType, FormStatus, Language, SessionStatus
from app.infrastructure.db.models import (
    AccountORM,
    ApiKeyORM,
    FormDefinitionORM,
    LiveSessionORM,
    UsageRecordORM,
)


def account_to_domain(o: AccountORM) -> Account:
    return Account(
        id=o.id,
        nom=o.nom,
        email_contact=o.email_contact,
        langue=Language(o.langue),
        persona_prompt=o.persona_prompt,
        voice_prompt=o.voice_prompt,
        actif=o.actif,
        allowed_origins=list(o.allowed_origins or []),
        date_creation=o.date_creation,
    )


def apply_account(o: AccountORM, e: Account) -> AccountORM:
    o.nom = e.nom
    o.email_contact = e.email_contact
    o.langue = e.langue.value
    o.persona_prompt = e.persona_prompt
    o.voice_prompt = e.voice_prompt
    o.actif = e.actif
    o.allowed_origins = list(e.allowed_origins)
    o.date_creation = e.date_creation
    return o


def apikey_to_domain(o: ApiKeyORM) -> ApiKey:
    return ApiKey(
        id=o.id,
        account_id=o.account_id,
        label=o.label,
        key_prefix=o.key_prefix,
        key_hash=o.key_hash,
        actif=o.actif,
        cree_a=o.cree_a,
    )


def _field_to_dict(f: FormField) -> dict:
    return {
        "name": f.name,
        "label": f.label,
        "type": f.type.value,
        "required": f.required,
        "enum_values": f.enum_values,
        "description": f.description,
    }


def _field_from_dict(d: dict) -> FormField:
    return FormField(
        name=d["name"],
        label=d["label"],
        type=FieldType(d["type"]),
        required=d.get("required", False),
        enum_values=d.get("enum_values", []),
        description=d.get("description", ""),
    )


def form_to_domain(o: FormDefinitionORM) -> FormDefinition:
    return FormDefinition(
        id=o.id,
        account_id=o.account_id,
        form_id=o.form_id,
        titre=o.titre,
        fields=[_field_from_dict(d) for d in (o.fields or [])],
        langue=Language(o.langue) if o.langue else None,
        version=o.version,
        statut=FormStatus(o.statut),
    )


def apply_form(o: FormDefinitionORM, e: FormDefinition) -> FormDefinitionORM:
    o.account_id = e.account_id
    o.form_id = e.form_id
    o.titre = e.titre
    o.fields = [_field_to_dict(f) for f in e.fields]
    o.langue = e.langue.value if e.langue else None
    o.version = e.version
    o.statut = e.statut.value
    return o


def session_to_domain(o: LiveSessionORM) -> LiveSession:
    return LiveSession(
        id=o.id,
        account_id=o.account_id,
        form_id=o.form_id,
        statut=SessionStatus(o.statut),
        cree_a=o.cree_a,
        expires_at=o.expires_at,
    )


def usage_to_domain(o: UsageRecordORM) -> UsageRecord:
    return UsageRecord(
        id=o.id, account_id=o.account_id, endpoint=o.endpoint, horodatage=o.horodatage
    )

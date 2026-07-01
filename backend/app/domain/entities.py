"""Entités du domaine (DATA-1.1).

Dataclasses pures (stdlib uniquement). Les invariants métier sont validés dans
`__post_init__` et lèvent une `ValidationError` du domaine — jamais une erreur HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.domain.errors import ValidationError
from app.domain.value_objects import (
    Confidence,
    FieldType,
    FormStatus,
    Language,
    SessionStatus,
)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class FormField:
    """Un champ d'un formulaire dynamique. `description` sert à la persona ET à l'extraction."""

    name: str
    label: str
    type: FieldType
    required: bool = False
    enum_values: list[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("Le nom d'un champ est obligatoire.")
        if self.type is FieldType.ENUM and not self.enum_values:
            raise ValidationError(f"Le champ enum {self.name!r} requiert des valeurs autorisées.")
        if self.type is not FieldType.ENUM and self.enum_values:
            raise ValidationError(f"Le champ {self.name!r} n'est pas de type enum mais a des valeurs.")


@dataclass
class FormDefinition:
    """Formulaire défini par l'Admin pour un compte (remplace le catalogue figé du v1)."""

    account_id: int
    form_id: str  # slug unique par compte (ex. "consultation")
    titre: str
    fields: list[FormField] = field(default_factory=list)
    langue: Language | None = None  # surcharge la langue du compte si fournie
    version: int = 1
    statut: FormStatus = FormStatus.DRAFT
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.form_id:
            raise ValidationError("form_id est obligatoire.")
        noms = [f.name for f in self.fields]
        if len(noms) != len(set(noms)):
            raise ValidationError("Noms de champs dupliqués dans le formulaire.")

    @property
    def required_fields(self) -> list[str]:
        return [f.name for f in self.fields if f.required]


@dataclass
class Account:
    """Compte client B2B (une application intégratrice)."""

    nom: str
    email_contact: str
    langue: Language = Language.FR
    persona_prompt: str = ""
    voice_prompt: str = ""
    actif: bool = True
    allowed_origins: list[str] = field(default_factory=list)  # CORS par compte (SEC-2.2)
    id: int | None = None
    date_creation: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.email_contact:
            raise ValidationError("L'email de contact est obligatoire.")


@dataclass
class ApiKey:
    """Clé API d'un compte — stockée HACHÉE (jamais en clair, cf. DATA-1.4)."""

    account_id: int
    key_prefix: str  # début de la clé, pour affichage/lookup (non secret)
    key_hash: str    # SHA-256 de la clé en clair
    label: str = "Clé principale"
    actif: bool = True
    id: int | None = None
    cree_a: datetime = field(default_factory=_now)


@dataclass
class LiveSession:
    """Session de dialogue vocal temps réel."""

    account_id: int
    form_id: str
    id: str = field(default_factory=lambda: str(uuid4()))
    statut: SessionStatus = SessionStatus.PENDING
    cree_a: datetime = field(default_factory=_now)
    expires_at: datetime | None = None


@dataclass
class UsageRecord:
    """Événement d'usage (métadonnée de facturation — aucune donnée de santé)."""

    account_id: int
    endpoint: str
    id: int | None = None
    horodatage: datetime = field(default_factory=_now)


@dataclass
class FieldValue:
    """Valeur extraite d'un champ + sa confiance."""

    valeur: object | None = None
    confiance: Confidence = Confidence.MANQUANT


@dataclass
class FormState:
    """État courant d'un formulaire en cours de remplissage (EPIC 8)."""

    values: dict[str, FieldValue] = field(default_factory=dict)

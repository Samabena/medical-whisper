"""Value objects du domaine — types fermés et immuables (aucune dépendance externe)."""

from __future__ import annotations

from enum import Enum


class Language(str, Enum):
    """Langue d'un compte / formulaire (conditionne persona, voix, extraction)."""

    EN = "en"
    FR = "fr"


class Confidence(str, Enum):
    """Niveau de confiance d'un champ extrait (repris du v1)."""

    CONFIANT = "confiant"
    INCERTAIN = "incertain"
    MANQUANT = "manquant"


class FieldType(str, Enum):
    """Type d'un champ de formulaire dynamique."""

    STRING = "string"
    TEXT = "text"
    DATE = "date"
    INT = "int"
    NUMBER = "number"  # flottant (ex. température 38.5, poids 72.4)
    ENUM = "enum"
    BOOL = "bool"


class FormStatus(str, Enum):
    """Cycle de publication d'un formulaire."""

    DRAFT = "draft"
    PUBLISHED = "published"


class SessionStatus(str, Enum):
    """Cycle de vie d'une session live."""

    PENDING = "pending"      # jeton émis, WS pas encore ouvert
    ACTIVE = "active"        # dialogue en cours
    COMPLETED = "completed"  # formulaire requis complété
    EXPIRED = "expired"      # jeton/TTL dépassé
    CLOSED = "closed"        # fermée (déconnexion / abandon)

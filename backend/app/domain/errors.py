"""Hiérarchie d'erreurs du domaine.

Ces erreurs sont **agnostiques du transport** : aucune référence à HTTP ou à FastAPI.
La couche `interface` les traduit en codes HTTP/WS homogènes (cf. interface/errors.py).
"""

from __future__ import annotations


class DomainError(Exception):
    """Erreur métier de base. Toutes les erreurs du domaine en héritent."""

    code: str = "domain_error"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.__doc__ or self.code
        super().__init__(self.detail)


class NotFoundError(DomainError):
    """Ressource introuvable."""

    code = "non_trouve"


class UnauthorizedError(DomainError):
    """Authentification absente ou invalide."""

    code = "non_autorise"


class ForbiddenError(DomainError):
    """Accès interdit pour cette ressource."""

    code = "interdit"


class ConflictError(DomainError):
    """Conflit d'état (ex. unicité violée)."""

    code = "conflit"


class ValidationError(DomainError):
    """Donnée invalide au regard d'une règle métier."""

    code = "validation"


class QuotaExceededError(DomainError):
    """Quota ou limite de débit dépassé."""

    code = "quota_depasse"


class ServiceUnavailableError(DomainError):
    """Dépendance externe (modèle, LLM) indisponible."""

    code = "service_indisponible"

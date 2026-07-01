"""Traduction des erreurs domaine → réponses HTTP homogènes `{erreur, detail}`.

C'est l'unique endroit où le domaine rencontre HTTP : la couche `interface` connaît
FastAPI, le domaine non (règle de dépendance).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.domain.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
    QuotaExceededError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationError,
)

_STATUS_PAR_ERREUR: dict[type[DomainError], int] = {
    ValidationError: 422,
    UnauthorizedError: 401,
    ForbiddenError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    QuotaExceededError: 429,
    ServiceUnavailableError: 503,
}


def _status_pour(exc: DomainError) -> int:
    for type_err, status in _STATUS_PAR_ERREUR.items():
        if isinstance(exc, type_err):
            return status
    return 400


def enregistrer_handlers(app: FastAPI) -> None:
    """Branche un handler unique qui mappe toute `DomainError` sur son code HTTP."""

    @app.exception_handler(DomainError)
    async def _handler(request: Request, exc: DomainError) -> JSONResponse:  # noqa: ARG001
        return JSONResponse(
            status_code=_status_pour(exc),
            content={"erreur": exc.code, "detail": exc.detail},
        )

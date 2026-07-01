"""Point d'entrée de l'API Voice-to-Form."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.admin.auth import verifier_admin_api
from app.admin.router import api_router as admin_api_router
from app.admin.router import ui_router as admin_ui_router
from app.config import get_settings
from app.routers import forms, sessions

logger = logging.getLogger(__name__)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verifier_cle_api(request: Request, cle: str | None = Depends(_api_key_header)) -> None:
    try:
        from app.admin.crud import verifier_cle_api_db
        from app.admin.database import get_session_factory
        Session = get_session_factory()
        with Session() as db:
            compte = verifier_cle_api_db(db, cle)
        if compte is not None:
            request.state.compte_id = compte.id
            return
    except Exception:
        pass
    settings = get_settings()
    if cle in settings.api_keys:
        request.state.compte_id = None
        return
    raise HTTPException(status_code=401, detail="Clé API invalide ou manquante.")


class UsageMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        method = request.method
        is_session_create = method == "POST" and path == "/v1/sessions"
        is_session_reply = method == "POST" and "/repondre" in path
        if (is_session_create or is_session_reply) and response.status_code < 300:
            compte_id = getattr(request.state, "compte_id", None)
            if compte_id:
                try:
                    from app.admin.crud import enregistrer_usage
                    from app.admin.database import get_session_factory
                    Session = get_session_factory()
                    with Session() as db:
                        endpoint = "session_reply" if is_session_reply else "session_create"
                        enregistrer_usage(db, compte_id, endpoint, is_session_reply)
                except Exception:
                    pass
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    debut = time.perf_counter()
    try:
        from app.admin.crud import creer_cle_depuis_claire, creer_compte, lister_comptes
        from app.admin.database import creer_tables, get_session_factory
        creer_tables()
        settings = get_settings()
        if settings.api_keys:
            Session = get_session_factory()
            with Session() as db:
                if not lister_comptes(db):
                    compte = creer_compte(db, "Compte par défaut", "admin@local")
                    for cle in settings.api_keys:
                        creer_cle_depuis_claire(db, compte.id, cle)
                    logger.info("Migration : %d clé(s) config importées.", len(settings.api_keys))
    except Exception as exc:
        logger.warning("Impossible d'initialiser la base admin : %s", exc)
    try:
        from app.services.stt import _get_model as _charger_stt
        _charger_stt()
    except Exception as exc:
        logger.warning("Impossible de précharger Whisper : %s", exc)
    try:
        from app.services.tts import _get_voice as _charger_tts
        _charger_tts()
    except Exception as exc:
        logger.warning("Impossible de précharger Piper : %s", exc)
    logger.info("Démarrage en %.2f s.", time.perf_counter() - debut)
    yield


app = FastAPI(title="Voice-to-Form API", lifespan=lifespan)
_settings = get_settings()
if _settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.add_middleware(SessionMiddleware, secret_key=_settings.admin_secret_key)
app.add_middleware(UsageMiddleware)
app.include_router(forms.router, prefix="/v1", dependencies=[Depends(verifier_cle_api)])
app.include_router(sessions.router, prefix="/v1", dependencies=[Depends(verifier_cle_api)])
app.include_router(admin_api_router, dependencies=[Depends(verifier_admin_api)])
app.include_router(admin_ui_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(404)
async def handler_404(request: Request, exc: Exception) -> JSONResponse:
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(status_code=404, content={"erreur": "non_trouve", "detail": detail})


@app.exception_handler(400)
async def handler_400(request: Request, exc: Exception) -> JSONResponse:
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(status_code=400, content={"erreur": "requete_invalide", "detail": detail})


@app.exception_handler(401)
async def handler_401(request: Request, exc: Exception) -> JSONResponse:
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(status_code=401, content={"erreur": "non_autorise", "detail": detail})


@app.exception_handler(422)
async def handler_422(request: Request, exc: Exception) -> JSONResponse:
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(status_code=422, content={"erreur": "validation", "detail": detail})


@app.exception_handler(503)
async def handler_503(request: Request, exc: Exception) -> JSONResponse:
    detail = getattr(exc, "detail", str(exc))
    return JSONResponse(status_code=503, content={"erreur": "service_indisponible", "detail": detail})

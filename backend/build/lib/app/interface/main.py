"""Point d'entrée FastAPI (CORE-0.1).

Assemble l'application : middlewares, handlers d'erreurs domaine, lifespan
(le warm-up du modèle viendra à l'EPIC 7). Les routers métier seront montés au fil
des EPICs via la composition root (`deps.py`).
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infrastructure.config import get_settings
from app.interface.errors import enregistrer_handlers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    debut = time.perf_counter()
    settings = get_settings()
    logger.info(
        "Démarrage — agent vocal=%s, langue par défaut=%s",
        settings.speech_agent,
        settings.default_language,
    )
    # EPIC 7 : warm-up du serveur modèle ici (pré-connexion WebSocket).
    logger.info("Prêt en %.3f s.", time.perf_counter() - debut)
    yield


def create_app() -> FastAPI:
    """Fabrique l'application (factory — facilite les tests et la configuration)."""
    settings = get_settings()
    app = FastAPI(title="Voice-to-Form Live API", version="2.0.0", lifespan=lifespan)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    enregistrer_handlers(app)

    @app.get("/health", tags=["Ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

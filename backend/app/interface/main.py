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
    from app.infrastructure.observability.logging import setup_logging

    setup_logging()
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

    from app.infrastructure.cache.memory_rate_limiter import InMemoryRateLimiter
    from app.interface.middleware import RateLimitMiddleware, SecurityHeadersMiddleware

    app.add_middleware(RateLimitMiddleware, limiter=InMemoryRateLimiter(settings.rate_limit_per_minute))
    app.add_middleware(SecurityHeadersMiddleware)

    enregistrer_handlers(app)

    from app.interface.api import admin, admin_accounts, admin_forms, integration, ops
    from app.interface.ws import live

    app.include_router(integration.router)
    app.include_router(admin.router)
    app.include_router(admin_accounts.router)
    app.include_router(admin_forms.router)
    app.include_router(ops.router)
    app.include_router(live.router)

    @app.get("/health", tags=["Ops"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

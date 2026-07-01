"""Composition root — câblage des adapters vers les ports (DI).

À ce stade (EPIC 0) le conteneur est vide : il sera peuplé au fil des EPICs
(repositories EPIC 1, agent vocal EPIC 6, extracteur EPIC 8). Centraliser ici le
câblage garde les cas d'usage ignorants des implémentations concrètes.
"""

from __future__ import annotations

from app.infrastructure.config import Settings, get_settings


def settings() -> Settings:
    """Dépendance FastAPI : réglages applicatifs."""
    return get_settings()

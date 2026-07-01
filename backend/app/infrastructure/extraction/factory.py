"""Sélection de l'extracteur plat selon la configuration (dev null / prod ollama)."""

from __future__ import annotations

from app.application.ports.llm import FlatExtractorPort
from app.infrastructure.config import Settings


def build_flat_extractor(settings: Settings) -> FlatExtractorPort:
    if settings.extractor_backend == "ollama":
        from app.infrastructure.extraction.ollama_flat_extractor import OllamaFlatExtractor

        return OllamaFlatExtractor(
            host=settings.ollama_host,
            model=settings.ollama_model,
            api_key=settings.ollama_api_key or None,
        )

    if settings.extractor_backend == "keyword":
        from app.infrastructure.extraction.keyword_extractor import KeywordFlatExtractor

        return KeywordFlatExtractor()

    from app.infrastructure.extraction.null_extractor import NullFlatExtractor

    return NullFlatExtractor()

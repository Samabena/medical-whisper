"""Service LLM (Ollama via langchain-ollama)."""

from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.0):
    """Retourne une instance ChatOllama configurée."""
    from langchain_ollama import ChatOllama
    settings = get_settings()
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
        client_kwargs={"headers": {"Authorization": f"Bearer {settings.ollama_api_key}"}},
    )

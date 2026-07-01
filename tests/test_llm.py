"""Tests du client LLM partagé (CORE-2)."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# ── Tests unitaires (langchain_ollama mocké) ──────────────────────────────────


def _mock_settings(
    api_key: str = "cle-test",
    base_url: str = "https://ollama.com",
    model: str = "gpt-oss:120b",
) -> MagicMock:
    """Crée un objet Settings factice."""
    s = MagicMock()
    s.ollama_api_key = api_key
    s.ollama_base_url = base_url
    s.ollama_model = model
    return s


def _mock_langchain_module() -> tuple[MagicMock, MagicMock]:
    """Retourne (module_factice, classe_ChatOllama_factice)."""
    mock_cls = MagicMock()
    mock_module = MagicMock()
    mock_module.ChatOllama = mock_cls
    return mock_module, mock_cls


def test_get_llm_parametres_corrects() -> None:
    """get_llm() doit instancier ChatOllama avec base_url, model, temperature et header."""
    mock_module, mock_cls = _mock_langchain_module()

    with (
        patch.dict(sys.modules, {"langchain_ollama": mock_module}),
        patch("app.services.llm.get_settings", return_value=_mock_settings()),
    ):
        from app.services.llm import get_llm

        get_llm(temperature=0.7)

    mock_cls.assert_called_once_with(
        base_url="https://ollama.com",
        model="gpt-oss:120b",
        temperature=0.7,
        client_kwargs={"headers": {"Authorization": "Bearer cle-test"}},
    )


def test_get_llm_temperature_zero() -> None:
    """La temperature par défaut doit être 0.0."""
    mock_module, mock_cls = _mock_langchain_module()

    with (
        patch.dict(sys.modules, {"langchain_ollama": mock_module}),
        patch("app.services.llm.get_settings", return_value=_mock_settings()),
    ):
        from app.services.llm import get_llm

        get_llm()

    _, kwargs = mock_cls.call_args
    assert kwargs.get("temperature", mock_cls.call_args[0][2] if mock_cls.call_args[0] else None) == 0.0 or mock_cls.call_args.kwargs["temperature"] == 0.0


def test_get_llm_header_authorization() -> None:
    """Le header Authorization doit contenir la clé API sous forme Bearer."""
    mock_module, mock_cls = _mock_langchain_module()

    with (
        patch.dict(sys.modules, {"langchain_ollama": mock_module}),
        patch("app.services.llm.get_settings", return_value=_mock_settings(api_key="ma-vraie-cle")),
    ):
        from app.services.llm import get_llm

        get_llm()

    call_kwargs = mock_cls.call_args.kwargs
    assert call_kwargs["client_kwargs"]["headers"]["Authorization"] == "Bearer ma-vraie-cle"


# ── Test d'intégration (LLM réel) ────────────────────────────────────────────


@pytest.mark.integration
def test_get_llm_repond() -> None:
    """ChatOllama doit retourner une réponse non vide avec une clé valide."""
    if not os.environ.get("OLLAMA_API_KEY"):
        pytest.skip("OLLAMA_API_KEY absente — test d'intégration ignoré")

    from app.services.llm import get_llm

    llm = get_llm(temperature=0.0)
    response = llm.invoke("Dis bonjour en une seule phrase.")

    assert response.content, "La réponse du LLM ne doit pas être vide"

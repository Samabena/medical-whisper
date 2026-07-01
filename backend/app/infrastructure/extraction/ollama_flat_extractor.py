"""Extracteur plat via Ollama (EXTR-8.1, prod) — implémente FlatExtractorPort.

Utilise les sorties structurées d'Ollama (paramètre `format` = schéma JSON) à
température 0. Ollama est auto-hébergeable → adapté aux données de santé (pas d'envoi à
un tiers). L'import d'`ollama` est paresseux pour ne pas peser sur le profil `null`.
"""

from __future__ import annotations

import json
import logging
import re

from app.application.forms.prompt_builder import build_extraction_prompt, build_flat_schema
from app.domain.entities import FormDefinition

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _parse_json_objet(contenu: str) -> dict[str, object]:
    """Parse le JSON renvoyé par le LLM, tolérant aux blocs ```json``` et au texte autour.

    Certains modèles (gpt-oss) n'appliquent pas strictement `format=schema` et enrobent
    le JSON dans un bloc Markdown ou ajoutent du texte. On récupère le premier objet JSON.
    """
    contenu = contenu.strip()
    fence = _FENCE.search(contenu)
    if fence:
        contenu = fence.group(1).strip()
    try:
        return json.loads(contenu)
    except (ValueError, TypeError):
        pass
    debut, fin = contenu.find("{"), contenu.rfind("}")
    if 0 <= debut < fin:
        return json.loads(contenu[debut : fin + 1])
    raise ValueError("aucun objet JSON exploitable")


class OllamaFlatExtractor:
    def __init__(self, host: str, model: str, api_key: str | None = None) -> None:
        from ollama import AsyncClient

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        self._client = AsyncClient(host=host, headers=headers)
        self._model = model

    async def extract(self, transcript: str, form: FormDefinition) -> dict[str, object]:
        if not transcript.strip():
            return {}
        schema = build_flat_schema(form)
        systeme = build_extraction_prompt(form)
        try:
            resp = await self._client.chat(
                model=self._model,
                messages=[
                    {"role": "system", "content": systeme},
                    {"role": "user", "content": transcript},
                ],
                format=schema,
                options={"temperature": 0},
            )
            data = _parse_json_objet(resp["message"]["content"])
        except Exception as exc:  # noqa: BLE001 — extraction best-effort, ne casse pas le live
            logger.warning("Extraction Ollama échouée : %s", exc)
            return {}
        return {k: v for k, v in data.items() if v is not None}

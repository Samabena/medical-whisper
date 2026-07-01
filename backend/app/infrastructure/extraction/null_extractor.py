"""Extracteur plat neutre — dev/offline (n'extrait rien).

Permet de faire tourner l'orchestration live sans LLM. Combiné à `FormExtractor`, il
laisse le formulaire vide ; le remplissage réel nécessite le backend `ollama`.
"""

from __future__ import annotations

from app.domain.entities import FormDefinition


class NullFlatExtractor:
    async def extract(self, transcript: str, form: FormDefinition) -> dict[str, object]:
        return {}

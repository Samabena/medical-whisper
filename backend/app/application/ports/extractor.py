"""Port d'extraction structurée (défini ici car l'orchestrateur en dépend ; impl EPIC 8).

Lit le transcript courant et met à jour l'état du formulaire `{champ: {valeur, confiance}}`,
sans écraser les champs déjà confiants (fusion).
"""

from __future__ import annotations

from typing import Protocol

from app.domain.entities import FormDefinition, FormState


class FormExtractorPort(Protocol):
    async def update(self, transcript: str, form: FormDefinition, partiel: FormState) -> FormState:
        ...

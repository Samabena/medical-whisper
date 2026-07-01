"""Port d'extraction « plate » par LLM (EXTR-8.1).

Le LLM renvoie une valeur scalaire par champ (ou absent) — ce que les modèles produisent
de façon fiable. La reconstruction `{valeur, confiance}` et la fusion sont faites en
application (`FormExtractor`), pas par le LLM. L'algorithme/fournisseur LLM reste un
détail d'infrastructure.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.entities import FormDefinition


class FlatExtractorPort(Protocol):
    async def extract(self, transcript: str, form: FormDefinition) -> dict[str, object]:
        """Renvoie {nom_champ: valeur_scalaire} pour les champs reconnus dans le transcript."""
        ...

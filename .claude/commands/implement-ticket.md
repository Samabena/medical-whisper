Implémente le ticket **$ARGUMENTS** du fichier `BACKLOG.md`.

## Étapes

1. Lis `BACKLOG.md` — trouve la section du ticket `$ARGUMENTS`, note ses **Tâches**, critères d'**Acceptation** et dépendances.
2. Parcours les fichiers existants (`app/`, `tests/`) pour comprendre l'état courant.
3. Implémente toutes les tâches du ticket en respectant les **Conventions de travail** définies dans le BACKLOG :
   - Python 3.10+, type hints partout, docstrings en français
   - `ruff` + `black` ; aucune variable inutilisée
   - Secrets uniquement via `.env` / `pydantic-settings` — jamais en dur
   - Code dans `app/`, tests dans `tests/`, un module par responsabilité
4. Écris le(s) test(s) `pytest` requis :
   - STT / TTS / LLM **mockés** en tests unitaires
   - Marqués `@pytest.mark.integration` pour les vrais appels (skippés sans clé/modèle)
5. Lance `pytest tests/ -m "not integration" -v` — corrige jusqu'à ce que tout soit vert.
6. **Arrête-toi ici** — ne commence pas les tickets suivants.

## Rappels structurels

| Couche       | Module cible                              |
|--------------|-------------------------------------------|
| Config       | `app/config.py`                           |
| STT          | `app/services/stt.py`                     |
| LLM          | `app/services/llm.py`                     |
| TTS          | `app/services/tts.py`                     |
| Extraction   | `app/services/extraction.py`              |
| Clarification| `app/services/clarification.py`           |
| Sessions     | `app/sessions/store.py`                   |
| Routers      | `app/routers/sessions.py`                 |
| Formulaires  | `app/schemas/forms.py`                    |
| Catalogue    | `app/catalog/forms_catalog.py`            |

Message de commit attendu : `[$ARGUMENTS] <description courte en français>`

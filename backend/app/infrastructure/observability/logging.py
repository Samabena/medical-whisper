"""Journalisation structurée JSON (OBS-10.2).

Les logs ne contiennent JAMAIS de contenu clinique (transcript, valeurs de formulaire) :
on corrèle par `session_id`/`account_id` seulement. `setup_logging()` est appelée au
démarrage de l'application (pas en import) pour ne pas perturber les tests.
"""

from __future__ import annotations

import json
import logging
import os

_CONTEXT_KEYS = ("session_id", "account_id", "endpoint", "latency_ms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {"level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for key in _CONTEXT_KEYS:
            if hasattr(record, key):
                data[key] = getattr(record, key)
        return json.dumps(data, ensure_ascii=False)


def setup_logging(level: str | None = None) -> None:
    level = level or os.environ.get("LOG_LEVEL", "INFO")
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

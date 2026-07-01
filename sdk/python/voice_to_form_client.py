"""SDK serveur Python pour Voice-to-Form Live (INT-5.3).

Usage server-to-server : garde la clé API côté backend. Dépend de `httpx`.
"""

from __future__ import annotations

from typing import Any

import httpx


class VoiceToFormError(RuntimeError):
    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self.payload = payload
        super().__init__(f"Voice-to-Form API {status}: {payload}")


class VoiceToFormClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {"X-API-Key": api_key}
        self._timeout = timeout

    def _request(self, method: str, path: str, **kw) -> dict:
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.request(method, f"{self._base}{path}", headers=self._headers, **kw)
        if resp.status_code >= 300:
            raise VoiceToFormError(resp.status_code, _safe_json(resp))
        return resp.json()

    def create_session(self, form_id: str) -> dict:
        """Crée une session live. Renvoie {session_id, ws_url, token, language, form_schema}."""
        return self._request("POST", "/v1/integration/sessions", json={"form_id": form_id})

    def get_result(self, session_id: str) -> dict:
        """Récupère le formulaire final. 404 tant que la session n'est pas terminée."""
        return self._request("GET", f"/v1/integration/sessions/{session_id}/result")


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text

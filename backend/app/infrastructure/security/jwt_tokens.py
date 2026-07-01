"""Service de jetons éphémères JWT (HS256) — implémente EphemeralTokenPort (INT-5.1).

Le jeton porte la session dans `aud`, un `jti` unique (anti-rejeu) et une `exp`.
La vérification valide signature + expiration et renvoie les claims ; la comparaison
session_id (path vs claim) et l'usage unique sont assurés à l'ouverture du WS (EPIC 7.1).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.application.ports.token_service import SessionToken, TokenClaims
from app.domain.errors import UnauthorizedError


class JwtTokenService:
    def __init__(self, secret: str, algorithm: str = "HS256") -> None:
        self._secret = secret
        self._alg = algorithm

    def mint(self, session_id: str, ttl_seconds: int) -> SessionToken:
        now = datetime.now(tz=timezone.utc)
        exp = now + timedelta(seconds=ttl_seconds)
        token = jwt.encode(
            {"aud": session_id, "jti": str(uuid.uuid4()), "iat": now, "exp": exp},
            self._secret,
            algorithm=self._alg,
        )
        return SessionToken(token=token, expires_at=exp)

    def verify(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._alg],
                options={"verify_aud": False},  # comparaison session_id faite par l'appelant
            )
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("Jeton de session expiré.") from exc
        except jwt.InvalidTokenError as exc:
            raise UnauthorizedError("Jeton de session invalide.") from exc
        return TokenClaims(session_id=payload["aud"], jti=payload["jti"])

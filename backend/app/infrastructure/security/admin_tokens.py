"""Jetons admin JWT — access (court) + refresh (long) (implémente AdminTokenService)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.domain.errors import UnauthorizedError

_ACCESS = "access"
_REFRESH = "refresh"


class JwtAdminTokenService:
    def __init__(
        self,
        secret: str,
        access_ttl_minutes: int = 30,
        refresh_ttl_days: int = 7,
        algorithm: str = "HS256",
    ) -> None:
        self._secret = secret
        self._alg = algorithm
        self._access_ttl = timedelta(minutes=access_ttl_minutes)
        self._refresh_ttl = timedelta(days=refresh_ttl_days)

    def _encode(self, subject: str, typ: str, ttl: timedelta) -> str:
        now = datetime.now(tz=timezone.utc)
        return jwt.encode(
            {"sub": subject, "typ": typ, "iat": now, "exp": now + ttl},
            self._secret,
            algorithm=self._alg,
        )

    def _decode(self, token: str, typ_attendu: str) -> str:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._alg])
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("Session admin expirée.") from exc
        except jwt.InvalidTokenError as exc:
            raise UnauthorizedError("Jeton admin invalide.") from exc
        if payload.get("typ") != typ_attendu:
            raise UnauthorizedError("Type de jeton admin incorrect.")
        return payload["sub"]

    def issue_pair(self, subject: str) -> tuple[str, str]:
        return (
            self._encode(subject, _ACCESS, self._access_ttl),
            self._encode(subject, _REFRESH, self._refresh_ttl),
        )

    def refresh(self, refresh_token: str) -> str:
        subject = self._decode(refresh_token, _REFRESH)
        return self._encode(subject, _ACCESS, self._access_ttl)

    def verify_access(self, token: str) -> str:
        return self._decode(token, _ACCESS)

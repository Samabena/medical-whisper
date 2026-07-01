"""Middlewares HTTP transverses (SEC-2.2) : en-têtes de sécurité + limitation de débit."""

from __future__ import annotations

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.application.ports.rate_limiter import RateLimiter


# CSP stricte par défaut : tout doit être same-origin.
_CSP_STRICTE = "default-src 'self'"

# Swagger UI / ReDoc chargent leurs assets (JS/CSS) depuis un CDN ET s'initialisent via
# un script inline : la CSP stricte les bloque → page blanche sur /docs. On assouplit la
# CSP UNIQUEMENT sur ces routes de documentation ; l'API et l'admin restent stricts.
_CSP_DOCS = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
    "worker-src 'self' blob:"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        path = request.url.path
        est_doc = path.startswith("/docs") or path.startswith("/redoc")
        response.headers["Content-Security-Policy"] = _CSP_DOCS if est_doc else _CSP_STRICTE
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter) -> None:
        super().__init__(app)
        self._limiter = limiter

    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        client = request.client.host if request.client else "anon"
        if not await self._limiter.allow(client):
            return JSONResponse(
                status_code=429,
                content={"erreur": "quota_depasse", "detail": "Trop de requêtes, réessayez plus tard."},
            )
        return await call_next(request)

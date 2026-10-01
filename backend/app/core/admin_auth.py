from __future__ import annotations

import hashlib
import hmac

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import settings
from app.core.response import error_response


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def verify_admin_token(authorization: str | None) -> bool:
    if not settings.ADMIN_AUTH_ENABLED:
        return True
    if not authorization or not authorization.startswith("Bearer "):
        return False
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return False
    actual = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expected = settings.ADMIN_API_TOKEN_HASH.get_secret_value().strip().lower()
    return bool(expected) and hmac.compare_digest(actual, expected)


class AdminWriteProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        protected = request.url.path.startswith("/api/") and request.method.upper() not in SAFE_METHODS
        if protected and not verify_admin_token(request.headers.get("Authorization")):
            return JSONResponse(
                status_code=401,
                content=error_response(message="admin authorization required", code=1),
                headers={"Cache-Control": "no-store"},
            )
        return await call_next(request)

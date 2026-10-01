import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.response import error_response
from app.core.security import sanitize_text

logger = logging.getLogger("backend_errors")


def _security_headers(request: Request) -> dict[str, str]:
    if request.url.path.startswith("/api/telegram-config"):
        return {"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"}
    return {}


class AppException(Exception):
    """Business exception containing a browser-safe message."""

    def __init__(self, message: str, status_code: int = 400, code: int = 1) -> None:
        safe_message = sanitize_text(message)
        super().__init__(safe_message)
        self.message = safe_message
        self.status_code = status_code
        self.code = code


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error("application_error status=%s message=%s", exc.status_code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(message=exc.message, code=exc.code),
            headers=_security_headers(request),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        message = sanitize_text(exc.detail) if isinstance(exc.detail, str) else "request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(message=message, code=1),
            headers=_security_headers(request),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first_error = errors[0] if errors else {}
        message = sanitize_text(first_error.get("msg", "validation error"))
        return JSONResponse(
            status_code=422,
            content=error_response(message=message, code=1),
            headers=_security_headers(request),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception method=%s path=%s error=%s",
            request.method,
            request.url.path,
            sanitize_text(exc),
        )
        return JSONResponse(
            status_code=500,
            content=error_response(message="internal server error", code=1),
            headers=_security_headers(request),
        )

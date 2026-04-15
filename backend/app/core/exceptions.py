from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.response import error_response


class AppException(Exception):
    """Business exception with optional HTTP status and custom code."""

    def __init__(self, message: str, status_code: int = 400, code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers for unified API output."""

    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(message=exc.message, code=exc.code),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(message=message, code=1),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first_error = errors[0] if errors else {}
        message = first_error.get("msg", "validation error")
        return JSONResponse(
            status_code=422,
            content=error_response(message=message, code=1),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_response(message="internal server error", code=1),
        )

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.database import initialize_database
from app.core.exceptions import register_exception_handlers
from app.core.response import success_response


def create_app() -> FastAPI:
    """Application factory for easier testing and future extension."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )
    register_exception_handlers(app)

    @app.on_event("startup")
    def on_startup() -> None:
        # Initialize database schema at startup.
        initialize_database()

    @app.get("/health", tags=["Health"])
    def health_check() -> dict:
        return success_response(data={"status": "ok"})

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()


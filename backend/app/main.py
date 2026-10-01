import logging

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.router import api_router
from app.core.admin_auth import AdminWriteProtectionMiddleware
from app.core.config import settings
from app.core.database import SessionLocal, engine, initialize_database
from app.core.migrations import current_schema_version
from app.core.exceptions import register_exception_handlers
from app.core.response import success_response
from app.core.startup_checks import run_startup_checks


def create_app() -> FastAPI:
    """Application factory for easier testing and future extension."""

    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL))
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )
    app.add_middleware(AdminWriteProtectionMiddleware)
    if settings.allowed_hosts_list != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list)
    register_exception_handlers(app)

    @app.on_event("startup")
    def on_startup() -> None:
        initialize_database()
        with SessionLocal() as db:
            app.state.config_validation = run_startup_checks(db)

    @app.get("/health", tags=["Health"])
    def health_check() -> dict:
        return success_response(
            data={
                "status": "ok",
                "database": "ok",
                "schema_version": current_schema_version(engine),
            }
        )

    app.include_router(api_router, prefix="/api")
    return app


app = create_app()

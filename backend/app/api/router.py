from fastapi import APIRouter

from app.api.dashboard import router as dashboard_router
from app.api.downloads import router as downloads_router
from app.api.logs import router as logs_router
from app.api.personal import router as personal_router
from app.api.settings import router as settings_router
from app.api.sync import router as sync_router
from app.api.telegram_config import router as telegram_config_router
from app.api.v1.router import v1_router

api_router = APIRouter()
api_router.include_router(dashboard_router)
api_router.include_router(downloads_router)
api_router.include_router(logs_router)
api_router.include_router(personal_router)
api_router.include_router(settings_router)
api_router.include_router(sync_router)
api_router.include_router(telegram_config_router)
api_router.include_router(v1_router, prefix="/v1")

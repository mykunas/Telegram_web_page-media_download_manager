from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success_response
from app.schemas.telegram_config import (
    CodeSubmitPayload,
    DownloadConfigPayload,
    PasswordSubmitPayload,
    TelegramConfigPayload,
)
from app.services.telegram_auth_service import telegram_auth_service
from app.services.telegram_config_service import (
    DOWNLOAD_SETTING_SPECS,
    TELEGRAM_SETTING_SPECS,
    build_telegram_auth_config,
    read_download_values,
    read_group_values,
    save_group_values,
)

router = APIRouter(prefix="/telegram-config", tags=["TelegramConfig"])


def _safe_auth_status(db: Session) -> dict:
    try:
        config = build_telegram_auth_config(db)
    except Exception:
        config = None
    return telegram_auth_service.status(config)


@router.get("")
def get_telegram_config(db: Session = Depends(get_db)) -> dict:
    telegram = read_group_values(db, TELEGRAM_SETTING_SPECS)
    download = read_download_values(db)
    session_status = _safe_auth_status(db)
    return success_response(
        data={
            "telegram": telegram,
            "download": download,
            "session_status": session_status,
        }
    )


@router.put("/telegram")
def save_telegram_config(payload: TelegramConfigPayload, db: Session = Depends(get_db)) -> dict:
    values = payload.model_dump()
    telegram = save_group_values(db, values, TELEGRAM_SETTING_SPECS)
    return success_response(data=telegram, message="telegram 配置已保存")


@router.put("/download")
def save_download_config(payload: DownloadConfigPayload, db: Session = Depends(get_db)) -> dict:
    data = payload.model_dump()
    values = {
        "DOWNLOAD_DIR": data["DOWNLOAD_DIR"],
        "TARGET_CHATS": data["TARGET_CHATS"],
        "ALLOW_EXTS": data["ALLOW_EXTS"],
        "DOWNLOAD_HISTORY": "true" if data["DOWNLOAD_HISTORY"] else "false",
        "HISTORY_LIMIT": str(data["HISTORY_LIMIT"]),
        "MAX_RETRIES": str(data["MAX_RETRIES"]),
        "RETRY_DELAY": str(data["RETRY_DELAY"]),
        "MAX_FILE_SIZE_MB": str(data["MAX_FILE_SIZE_MB"]),
    }
    save_group_values(db, values, DOWNLOAD_SETTING_SPECS)
    return success_response(data=read_download_values(db), message="下载配置已保存")


@router.post("/auth/start")
def start_authorization(db: Session = Depends(get_db)) -> dict:
    config = build_telegram_auth_config(db)
    status = telegram_auth_service.start_authorization(config)
    return success_response(data=status, message="验证码已发送")


@router.post("/auth/code")
def submit_code(payload: CodeSubmitPayload, db: Session = Depends(get_db)) -> dict:
    _ = db
    status = telegram_auth_service.submit_code(payload.code)
    return success_response(data=status, message="验证码已提交")


@router.post("/auth/password")
def submit_password(payload: PasswordSubmitPayload, db: Session = Depends(get_db)) -> dict:
    _ = db
    status = telegram_auth_service.submit_password(payload.password)
    return success_response(data=status, message="二步验证密码已提交")


@router.get("/auth/status")
def get_auth_status(db: Session = Depends(get_db)) -> dict:
    status = _safe_auth_status(db)
    return success_response(data=status)


@router.post("/auth/disconnect")
def disconnect_session(db: Session = Depends(get_db)) -> dict:
    try:
        config = build_telegram_auth_config(db)
    except Exception:
        config = None
    status = telegram_auth_service.disconnect(config)
    return success_response(data=status, message="会话已断开")

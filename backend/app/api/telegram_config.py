from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.response import success_response
from app.core.rate_limit import AUTH_START_LIMIT, AUTH_VERIFY_LIMIT, CONFIG_WRITE_LIMIT
from app.core.security import mask_phone, sanitize_text
from app.schemas.telegram_config import (
    CodeSubmitPayload,
    DownloadConfigPayload,
    PasswordSubmitPayload,
    SecretClearPayload,
    SessionDeletePayload,
    TelegramConfigPayload,
)
from app.services.telegram_auth_service import telegram_auth_service
from app.services.telegram_config_service import (
    build_telegram_auth_config,
    clear_secret_values,
    config_change_effect,
    read_download_values,
    read_telegram_public_view,
    save_runtime_values,
    save_secret_values,
)

router = APIRouter(prefix="/telegram-config", tags=["TelegramConfig"])
audit_logger = logging.getLogger("security_audit")


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"


def _safe_auth_status(db: Session) -> dict:
    try:
        config = build_telegram_auth_config(db)
    except Exception:
        config = None
    status = telegram_auth_service.status(config)
    return {
        "step": status.get("step", "idle"),
        "authorized": bool(status.get("authorized")),
        "message": sanitize_text(status.get("message", "")),
        "phone_number": mask_phone(status.get("phone_number", "")),
        "session_exists": bool(status.get("session_exists")),
        "user_id": status.get("user_id"),
        "user_name": status.get("user_name"),
    }


def _security_status(telegram: dict, auth_status: dict) -> dict:
    configured = all(
        telegram[key]["configured"] for key in ("API_ID", "API_HASH", "PHONE_NUMBER", "SESSION_NAME")
    )
    return {
        "telegram_credentials_configured": configured,
        "session_exists": bool(telegram.get("session_exists") or auth_status.get("session_exists")),
        "debug_enabled": bool(settings.DEBUG),
        "admin_protection_enabled": bool(getattr(settings, "ADMIN_AUTH_ENABLED", False)),
        "config_validation_status": "valid" if configured else "incomplete",
    }


@router.get("")
def get_telegram_config(response: Response, db: Session = Depends(get_db)) -> dict:
    _no_store(response)
    telegram = read_telegram_public_view(db)
    download = read_download_values(db)
    session_status = _safe_auth_status(db)
    return success_response(
        data={
            "telegram": telegram,
            "download": download,
            "session_status": session_status,
            "security_status": _security_status(telegram, session_status),
        }
    )


@router.put("/telegram", dependencies=[Depends(CONFIG_WRITE_LIMIT)])
def save_telegram_config(
    payload: TelegramConfigPayload,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    _no_store(response)
    updated_keys = save_secret_values(db, payload.model_dump())
    for key in updated_keys:
        audit_logger.info("config_change key=%s action=updated result=success secret=true", key)
    effect = config_change_effect(updated_keys)
    return success_response(
        data={
            "config": read_telegram_public_view(db),
            "updated": bool(updated_keys),
            "updated_keys": updated_keys,
            **effect,
        },
        message="Telegram configuration updated",
    )


@router.put("/download", dependencies=[Depends(CONFIG_WRITE_LIMIT)])
def save_download_config(payload: DownloadConfigPayload, db: Session = Depends(get_db)) -> dict:
    values = payload.model_dump()
    config = save_runtime_values(db, values)
    for key in values:
        audit_logger.info("config_change key=%s action=updated result=success secret=false", key)
    return success_response(
        data={
            "config": config,
            "updated": True,
            **config_change_effect(values.keys()),
        },
        message="Download configuration updated",
    )


@router.delete("/credentials/{key}", dependencies=[Depends(CONFIG_WRITE_LIMIT)])
def clear_telegram_credential(
    key: str,
    payload: SecretClearPayload,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    _no_store(response)
    expected = f"CLEAR_{key.upper()}"
    if payload.confirm != expected:
        from app.core.exceptions import AppException

        raise AppException(f"confirmation must equal {expected}", status_code=400)
    cleared = clear_secret_values(db, [key.upper()])
    audit_logger.info("config_change key=%s action=cleared result=success secret=true", key.upper())
    return success_response(
        data={
            "config": read_telegram_public_view(db),
            "updated": True,
            "cleared_keys": cleared,
            **config_change_effect(cleared),
        },
        message="Credential cleared",
    )


@router.post("/auth/start", dependencies=[Depends(AUTH_START_LIMIT)])
def start_authorization(response: Response, db: Session = Depends(get_db)) -> dict:
    _no_store(response)
    config = build_telegram_auth_config(db)
    status = telegram_auth_service.start_authorization(config)
    return success_response(data=_safe_status_payload(status), message="Verification code sent")


@router.post("/auth/code", dependencies=[Depends(AUTH_VERIFY_LIMIT)])
def submit_code(payload: CodeSubmitPayload, response: Response, db: Session = Depends(get_db)) -> dict:
    _ = db
    _no_store(response)
    status = telegram_auth_service.submit_code(payload.code)
    return success_response(data=_safe_status_payload(status), message="Verification code submitted")


@router.post("/auth/password", dependencies=[Depends(AUTH_VERIFY_LIMIT)])
def submit_password(payload: PasswordSubmitPayload, response: Response, db: Session = Depends(get_db)) -> dict:
    _ = db
    _no_store(response)
    status = telegram_auth_service.submit_password(payload.password)
    return success_response(data=_safe_status_payload(status), message="Two-factor password submitted")


@router.get("/auth/status")
def get_auth_status(response: Response, db: Session = Depends(get_db)) -> dict:
    _no_store(response)
    return success_response(data=_safe_auth_status(db))


@router.post("/auth/disconnect", dependencies=[Depends(CONFIG_WRITE_LIMIT)])
def disconnect_session(response: Response, db: Session = Depends(get_db)) -> dict:
    _no_store(response)
    try:
        config = build_telegram_auth_config(db)
    except Exception:
        config = None
    status = telegram_auth_service.disconnect(config)
    audit_logger.info("telegram_session action=disconnect result=success")
    return success_response(data=_safe_status_payload(status), message="Client disconnected; session retained")


@router.delete("/session", dependencies=[Depends(CONFIG_WRITE_LIMIT)])
def delete_session(
    payload: SessionDeletePayload,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    _no_store(response)
    config = build_telegram_auth_config(db)
    status = telegram_auth_service.delete_session(config, confirmation=payload.confirm)
    audit_logger.info("telegram_session action=delete result=success")
    return success_response(data=_safe_status_payload(status), message="Telegram session deleted")


def _safe_status_payload(status: dict) -> dict:
    return {
        "step": status.get("step", "idle"),
        "authorized": bool(status.get("authorized")),
        "message": sanitize_text(status.get("message", "")),
        "phone_number": mask_phone(status.get("phone_number", "")),
        "session_exists": bool(status.get("session_exists")),
        "user_id": status.get("user_id"),
        "user_name": status.get("user_name"),
    }

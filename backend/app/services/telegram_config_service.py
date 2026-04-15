from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models import AppSetting


@dataclass(frozen=True)
class SettingSpec:
    default: str | None
    value_type: str
    description: str


TELEGRAM_SETTING_SPECS: dict[str, SettingSpec] = {
    "API_ID": SettingSpec(default="", value_type="string", description="Telegram API ID"),
    "API_HASH": SettingSpec(default="", value_type="string", description="Telegram API HASH"),
    "PHONE_NUMBER": SettingSpec(default="", value_type="string", description="Telegram 登录手机号"),
    "SESSION_NAME": SettingSpec(default="/app/session/telegram_user", value_type="string", description="Telegram 会话名"),
}

DOWNLOAD_SETTING_SPECS: dict[str, SettingSpec] = {
    "DOWNLOAD_DIR": SettingSpec(default="/downloads", value_type="string", description="下载目录"),
    "TARGET_CHATS": SettingSpec(default="", value_type="string", description="目标频道/群组，逗号分隔"),
    "ALLOW_EXTS": SettingSpec(
        default=".mp4,.mkv,.mov,.avi,.jpg,.jpeg,.png,.webp",
        value_type="string",
        description="允许下载的后缀名，逗号分隔",
    ),
    "DOWNLOAD_HISTORY": SettingSpec(default="true", value_type="boolean", description="是否下载历史消息"),
    "HISTORY_LIMIT": SettingSpec(default="2000", value_type="integer", description="历史消息下载上限"),
    "MAX_RETRIES": SettingSpec(default="3", value_type="integer", description="下载失败重试次数"),
    "RETRY_DELAY": SettingSpec(default="5", value_type="integer", description="每次重试等待秒数"),
    "MAX_FILE_SIZE_MB": SettingSpec(default="0", value_type="integer", description="最大文件大小（MB，0 表示不限制）"),
}

ALL_SETTING_SPECS: dict[str, SettingSpec] = {
    **TELEGRAM_SETTING_SPECS,
    **DOWNLOAD_SETTING_SPECS,
}


@dataclass(frozen=True)
class TelegramAuthConfig:
    api_id: int
    api_hash: str
    phone_number: str
    session_name: str


def _now() -> datetime:
    return datetime.now(UTC)


def ensure_required_settings(db: Session) -> dict[str, AppSetting]:
    keys = list(ALL_SETTING_SPECS.keys())
    rows = db.query(AppSetting).filter(AppSetting.key.in_(keys)).all()
    row_map = {row.key: row for row in rows}

    created = False
    for key, spec in ALL_SETTING_SPECS.items():
        if key in row_map:
            continue
        row = AppSetting(
            key=key,
            value=spec.default,
            value_type=spec.value_type,
            description=spec.description,
            updated_at=_now(),
        )
        db.add(row)
        db.flush()
        row_map[key] = row
        created = True

    if created:
        db.commit()
    return row_map


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def read_group_values(db: Session, specs: dict[str, SettingSpec]) -> dict[str, str]:
    row_map = ensure_required_settings(db)
    return {key: _safe_str(row_map[key].value) for key in specs}


def read_download_values(db: Session) -> dict[str, Any]:
    values = read_group_values(db, DOWNLOAD_SETTING_SPECS)
    return {
        "DOWNLOAD_DIR": values["DOWNLOAD_DIR"],
        "TARGET_CHATS": values["TARGET_CHATS"],
        "ALLOW_EXTS": values["ALLOW_EXTS"],
        "DOWNLOAD_HISTORY": values["DOWNLOAD_HISTORY"].strip().lower() in {"1", "true", "yes", "on"},
        "HISTORY_LIMIT": int(values["HISTORY_LIMIT"] or 0),
        "MAX_RETRIES": int(values["MAX_RETRIES"] or 0),
        "RETRY_DELAY": int(values["RETRY_DELAY"] or 0),
        "MAX_FILE_SIZE_MB": int(values["MAX_FILE_SIZE_MB"] or 0),
    }


def save_group_values(db: Session, values: dict[str, Any], specs: dict[str, SettingSpec]) -> dict[str, str]:
    row_map = ensure_required_settings(db)
    now = _now()

    for key, raw_value in values.items():
        if key not in specs:
            raise AppException(f"unsupported setting key: {key}", status_code=400)
        row = row_map[key]
        row.value = None if raw_value is None else str(raw_value)
        row.value_type = specs[key].value_type
        row.description = specs[key].description
        row.updated_at = now

    db.commit()
    return {key: _safe_str(row_map[key].value) for key in specs}


def build_telegram_auth_config(db: Session) -> TelegramAuthConfig:
    values = read_group_values(db, TELEGRAM_SETTING_SPECS)

    api_id_raw = values["API_ID"].strip()
    api_hash = values["API_HASH"].strip()
    phone_number = values["PHONE_NUMBER"].strip()
    session_name = values["SESSION_NAME"].strip()

    if not api_id_raw or not api_hash or not phone_number or not session_name:
        raise AppException("请先完整配置 API_ID、API_HASH、PHONE_NUMBER、SESSION_NAME", status_code=400)

    try:
        api_id = int(api_id_raw)
    except ValueError as exc:
        raise AppException("API_ID 必须是整数", status_code=400) from exc

    return TelegramAuthConfig(
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone_number,
        session_name=session_name,
    )

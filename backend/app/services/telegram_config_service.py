from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.core.config_registry import (
    CONFIG_REGISTRY,
    DATABASE_KEYS,
    DOWNLOAD_KEYS,
    TELEGRAM_KEYS,
    decode_storage_value,
    encode_storage_value,
    get_definition,
    validate_config_value,
    validate_update_batch,
)
from app.core.exceptions import AppException
from app.core.security import secret_metadata
from app.models import AppSetting


@dataclass(frozen=True, slots=True)
class TelegramAuthConfig:
    api_id: int
    api_hash: str
    phone_number: str
    session_name: str


def _now() -> datetime:
    return datetime.now(UTC)


def _default_storage_value(key: str) -> str:
    definition = get_definition(key)
    if definition.default in (None, ""):
        return ""
    return encode_storage_value(key, definition.default)


def ensure_required_settings(
    db: Session,
    keys: Iterable[str] = DATABASE_KEYS,
    *,
    commit: bool = True,
) -> dict[str, AppSetting]:
    resolved_keys = tuple(keys)
    rows = db.query(AppSetting).filter(AppSetting.key.in_(resolved_keys)).all()
    row_map = {row.key: row for row in rows}
    created = False

    for key in resolved_keys:
        if key in row_map:
            continue
        definition = get_definition(key)
        row = AppSetting(
            key=key,
            value=_default_storage_value(key),
            value_type=definition.value_type,
            description=definition.description,
            updated_at=_now(),
        )
        db.add(row)
        db.flush()
        row_map[key] = row
        created = True

    if created and commit:
        db.commit()
    return row_map


def resolve_raw_values(db: Session, keys: Iterable[str]) -> dict[str, str]:
    resolved_keys = tuple(keys)
    row_map = ensure_required_settings(db, resolved_keys)
    values: dict[str, str] = {}
    for key in resolved_keys:
        db_value = row_map[key].value
        if db_value is not None and str(db_value).strip() != "":
            values[key] = str(db_value)
            continue
        env_value = os.getenv(key)
        if env_value is not None and env_value.strip() != "":
            values[key] = env_value
            continue
        values[key] = _default_storage_value(key)
    return values


def read_group_values(db: Session, keys: Iterable[str]) -> dict[str, Any]:
    raw_values = resolve_raw_values(db, keys)
    return {key: decode_storage_value(key, raw_values[key]) for key in raw_values}


def read_download_values(db: Session) -> dict[str, Any]:
    values = read_group_values(db, DOWNLOAD_KEYS)
    return {
        "DOWNLOAD_DIR": values["DOWNLOAD_DIR"],
        "TARGET_CHATS": ",".join(values["TARGET_CHATS"]),
        "ALLOW_EXTS": ",".join(values["ALLOW_EXTS"]),
        "DOWNLOAD_HISTORY": values["DOWNLOAD_HISTORY"],
        "HISTORY_LIMIT": values["HISTORY_LIMIT"],
        "MAX_RETRIES": values["MAX_RETRIES"],
        "RETRY_DELAY": values["RETRY_DELAY"],
        "MAX_FILE_SIZE_MB": values["MAX_FILE_SIZE_MB"],
    }


def read_telegram_public_view(db: Session) -> dict[str, Any]:
    values = resolve_raw_values(db, TELEGRAM_KEYS)
    session_name = values["SESSION_NAME"]
    session_file = Path(f"{session_name}.session") if session_name else None
    return {
        "API_ID": secret_metadata(values["API_ID"], kind="api_id"),
        "API_HASH": secret_metadata(values["API_HASH"]),
        "PHONE_NUMBER": secret_metadata(values["PHONE_NUMBER"], kind="phone"),
        "SESSION_NAME": secret_metadata(session_name, kind="session"),
        "session_exists": bool(session_file and session_file.is_file()),
    }


def _write_normalized_values(db: Session, normalized: dict[str, str]) -> dict[str, AppSetting]:
    row_map = ensure_required_settings(db, normalized.keys(), commit=False)
    now = _now()
    try:
        for key, value in normalized.items():
            definition = get_definition(key)
            row = row_map[key]
            row.value = value
            row.value_type = definition.value_type
            row.description = definition.description
            row.updated_at = now
        db.commit()
        for key in normalized:
            db.refresh(row_map[key])
    except Exception:
        db.rollback()
        raise
    return row_map


def save_runtime_values(db: Session, values: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_update_batch(values, allow_secrets=False)
    try:
        _write_normalized_values(db, normalized)
    except AppException:
        raise
    except Exception as exc:
        raise AppException("configuration update failed", status_code=500) from exc
    return read_download_values(db)


def save_secret_values(db: Session, values: dict[str, Any]) -> list[str]:
    # Write-only semantics: an omitted, null or empty field keeps the old value.
    replacements = {
        key: value
        for key, value in values.items()
        if key in TELEGRAM_KEYS and value is not None and str(value).strip() != ""
    }
    if not replacements:
        return []

    normalized = validate_update_batch(replacements, allow_secrets=True)
    try:
        _write_normalized_values(db, normalized)
    except AppException:
        raise
    except Exception as exc:
        raise AppException("credential update failed", status_code=500) from exc
    return list(normalized.keys())


def clear_secret_values(db: Session, keys: Iterable[str]) -> list[str]:
    resolved_keys = tuple(keys)
    for key in resolved_keys:
        definition = get_definition(key)
        if not definition.secret or key not in TELEGRAM_KEYS:
            raise AppException(f"secret cannot be cleared through this API: {key}", status_code=400)
    row_map = ensure_required_settings(db, resolved_keys, commit=False)
    try:
        for key in resolved_keys:
            row_map[key].value = ""
            row_map[key].updated_at = _now()
        db.commit()
    except Exception as exc:
        db.rollback()
        raise AppException("credential clear failed", status_code=500) from exc
    return list(resolved_keys)


def build_telegram_auth_config(db: Session) -> TelegramAuthConfig:
    values = resolve_raw_values(db, TELEGRAM_KEYS)
    missing = [key for key, value in values.items() if not str(value).strip()]
    if missing:
        raise AppException("Telegram credentials are incomplete", status_code=400)

    validated = {key: validate_config_value(key, value) for key, value in values.items()}
    return TelegramAuthConfig(
        api_id=validated["API_ID"],
        api_hash=validated["API_HASH"],
        phone_number=validated["PHONE_NUMBER"],
        session_name=validated["SESSION_NAME"],
    )


def config_change_effect(keys: Iterable[str]) -> dict[str, bool]:
    definitions = [CONFIG_REGISTRY[key] for key in keys]
    return {
        "restart_required": any(item.restart_required for item in definitions),
        "worker_reload_required": any(item.worker_reload_required for item in definitions),
    }

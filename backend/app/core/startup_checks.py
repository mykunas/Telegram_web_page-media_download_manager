from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.config_registry import DOWNLOAD_KEYS, TELEGRAM_KEYS, decode_storage_value
from app.core.database import engine
from app.core.database_health import inspect_database
from app.services.telegram_config_service import resolve_raw_values

logger = logging.getLogger("startup_config")


def _directory_check(path: Path, label: str, result: dict[str, list[str]]) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        result["fatal"].append(f"{label} directory cannot be created")
        return
    if not path.is_dir() or not os.access(path, os.W_OK):
        result["fatal"].append(f"{label} directory is not writable")
    else:
        result["info"].append(f"{label} directory is writable")


def run_startup_checks(db: Session) -> dict[str, Any]:
    result: dict[str, list[str]] = {"fatal": [], "warning": [], "info": []}

    if settings.DATABASE_URL.startswith("sqlite:///"):
        database_path = Path(settings.DATABASE_URL.replace("sqlite:///", "", 1))
        _directory_check(database_path.parent, "database", result)
    _directory_check(Path(settings.SESSION_DIR), "session", result)
    _directory_check(Path(settings.DOWNLOAD_ROOT), "download", result)

    telegram_raw = resolve_raw_values(db, TELEGRAM_KEYS)
    missing = [key for key, value in telegram_raw.items() if not str(value).strip()]
    if missing:
        result["warning"].append("Telegram credentials are incomplete")
    else:
        try:
            for key, value in telegram_raw.items():
                decode_storage_value(key, value)
            result["info"].append("Telegram credential format is valid")
        except Exception:
            result["warning"].append("Telegram credential format is invalid")

    runtime_raw = resolve_raw_values(db, DOWNLOAD_KEYS)
    try:
        runtime = {key: decode_storage_value(key, value) for key, value in runtime_raw.items()}
        result["info"].append("Runtime configuration is valid")
        if not runtime["TARGET_CHATS"]:
            result["warning"].append("TARGET_CHATS is empty")
    except Exception:
        result["warning"].append("Runtime configuration contains invalid values")

    if settings.DEBUG:
        result["warning"].append("DEBUG is enabled; do not expose this instance publicly")
    else:
        result["info"].append("DEBUG is disabled")

    if settings.ADMIN_AUTH_ENABLED:
        result["info"].append("Admin write protection is enabled")
    else:
        result["warning"].append("Admin write protection is disabled")

    try:
        database_health = inspect_database(engine)
        if database_health["valid"]:
            result["info"].append(
                f"database integrity is valid at schema version {database_health['schema_version']}"
            )
        else:
            result["fatal"].append("database integrity check failed")
    except Exception:
        result["fatal"].append("database integrity check could not be completed")

    for level, messages in result.items():
        log_method = getattr(logger, "error" if level == "fatal" else level)
        for message in messages:
            log_method("startup_check level=%s message=%s", level, message)

    if result["fatal"]:
        raise RuntimeError("fatal startup configuration check failed")
    return {**result, "valid": not result["fatal"]}

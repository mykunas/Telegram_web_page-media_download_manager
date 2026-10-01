from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Callable

from app.core.exceptions import AppException


class ConfigCategory(str, Enum):
    BOOTSTRAP = "bootstrap"
    RUNTIME = "runtime"
    SECRET = "secret"


Validator = Callable[[Any], Any]


@dataclass(frozen=True, slots=True)
class ConfigDefinition:
    key: str
    value_type: str
    category: ConfigCategory
    default: Any
    required: bool
    secret: bool
    runtime_editable: bool
    restart_required: bool
    worker_reload_required: bool
    description: str
    validator: Validator


def _string(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _positive_api_id(value: Any) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError("API_ID must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError("API_ID must be a positive integer")
    return parsed


def _api_hash(value: Any) -> str:
    parsed = _string(value).lower()
    if not re.fullmatch(r"[0-9a-f]{32}", parsed):
        raise ValueError("API_HASH must be 32 hexadecimal characters")
    return parsed


def _phone(value: Any) -> str:
    parsed = re.sub(r"[\s()-]", "", _string(value))
    if not re.fullmatch(r"\+[1-9]\d{6,14}", parsed):
        raise ValueError("PHONE_NUMBER must use international format, for example +8613800000000")
    return parsed


def _bounded_integer(minimum: int, maximum: int) -> Validator:
    def validate(value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("value must be an integer") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"value must be between {minimum} and {maximum}")
        return parsed

    return validate


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = _string(value).lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("value must be a boolean")


def _csv(value: Any) -> list[str]:
    items = value if isinstance(value, (list, tuple, set)) else _string(value).split(",")
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        parsed = _string(item)
        if not parsed or parsed in seen:
            continue
        seen.add(parsed)
        result.append(parsed)
    return result


def _extensions(value: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in _csv(value):
        parsed = item.lower()
        if not parsed.startswith("."):
            parsed = f".{parsed}"
        if not re.fullmatch(r"\.[a-z0-9][a-z0-9._+-]{0,15}", parsed):
            raise ValueError(f"invalid file extension: {item}")
        if parsed not in seen:
            seen.add(parsed)
            result.append(parsed)
    if not result:
        raise ValueError("ALLOW_EXTS must contain at least one extension")
    return result


def _safe_posix_path(value: Any, roots: tuple[str, ...], *, allow_root: bool) -> str:
    raw = _string(value)
    if not raw or "\x00" in raw:
        raise ValueError("path cannot be empty")
    path = PurePosixPath(raw)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("path must be absolute and cannot contain '..'")
    normalized = str(path)
    for root in roots:
        root_path = PurePosixPath(root)
        if path == root_path:
            if allow_root:
                return normalized
            raise ValueError(f"path must be a child of {root}")
        if root_path in path.parents:
            return normalized
    raise ValueError(f"path must stay within: {', '.join(roots)}")


def _download_dir(value: Any) -> str:
    return _safe_posix_path(value, ("/app/downloads", "/downloads"), allow_root=True)


def _session_name(value: Any) -> str:
    raw = _string(value)
    if raw.endswith(".session"):
        raw = raw[: -len(".session")]
    return _safe_posix_path(raw, ("/app/session",), allow_root=False)


def _data_file(value: Any) -> str:
    return _safe_posix_path(value, ("/app/data",), allow_root=False)


def _log_file(value: Any) -> str:
    return _safe_posix_path(value, ("/app/logs",), allow_root=False)


def _log_level(value: Any) -> str:
    parsed = _string(value).upper()
    if parsed not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
    return parsed


def _hosts(value: Any) -> list[str]:
    hosts = _csv(value)
    return hosts or ["*"]


def _sha256_hash(value: Any) -> str:
    parsed = _string(value).lower()
    if parsed and not re.fullmatch(r"[0-9a-f]{64}", parsed):
        raise ValueError("value must be an empty string or a 64-character SHA-256 hex digest")
    return parsed


CONFIG_REGISTRY: dict[str, ConfigDefinition] = {}


def _register(definition: ConfigDefinition) -> None:
    CONFIG_REGISTRY[definition.key] = definition


def _define(
    key: str,
    value_type: str,
    category: ConfigCategory,
    default: Any,
    *,
    required: bool = False,
    secret: bool = False,
    runtime_editable: bool = False,
    restart_required: bool = False,
    worker_reload_required: bool = False,
    description: str,
    validator: Validator = _string,
) -> None:
    _register(
        ConfigDefinition(
            key=key,
            value_type=value_type,
            category=category,
            default=default,
            required=required,
            secret=secret,
            runtime_editable=runtime_editable,
            restart_required=restart_required,
            worker_reload_required=worker_reload_required,
            description=description,
            validator=validator,
        )
    )


# Bootstrap configuration: environment/Docker only.
_define("DATABASE_URL", "string", ConfigCategory.BOOTSTRAP, "sqlite:///./data/app.db", required=True, restart_required=True, description="SQLAlchemy database URL")
_define("DEBUG", "boolean", ConfigCategory.BOOTSTRAP, False, restart_required=True, description="Development debug mode", validator=_boolean)
_define("LOG_LEVEL", "string", ConfigCategory.BOOTSTRAP, "INFO", restart_required=True, description="Application log level", validator=_log_level)
_define("ALLOWED_HOSTS", "json", ConfigCategory.BOOTSTRAP, ["*"], restart_required=True, description="Accepted HTTP Host headers", validator=_hosts)
_define("ADMIN_AUTH_ENABLED", "boolean", ConfigCategory.BOOTSTRAP, False, restart_required=True, description="Protect state-changing API calls", validator=_boolean)
_define("ADMIN_API_TOKEN_HASH", "string", ConfigCategory.SECRET, "", secret=True, restart_required=True, description="SHA-256 hash of the admin bearer token", validator=_sha256_hash)
_define("HASH_INDEX_FILE", "string", ConfigCategory.BOOTSTRAP, "/app/data/hash_index.json", restart_required=True, description="Worker hash index file", validator=_data_file)
_define("LOG_FILE", "string", ConfigCategory.BOOTSTRAP, "/app/logs/downloader.log", restart_required=True, description="Worker log file", validator=_log_file)

# Telegram credentials and session identity. Empty update values mean keep existing.
_define("API_ID", "integer", ConfigCategory.SECRET, "", required=True, secret=True, runtime_editable=True, worker_reload_required=True, description="Telegram API ID", validator=_positive_api_id)
_define("API_HASH", "string", ConfigCategory.SECRET, "", required=True, secret=True, runtime_editable=True, worker_reload_required=True, description="Telegram API hash", validator=_api_hash)
_define("PHONE_NUMBER", "string", ConfigCategory.SECRET, "", required=True, secret=True, runtime_editable=True, worker_reload_required=True, description="Telegram phone number", validator=_phone)
_define("SESSION_NAME", "string", ConfigCategory.SECRET, "/app/session/telegram_user", required=True, secret=True, runtime_editable=True, worker_reload_required=True, description="Telegram session path without extension", validator=_session_name)

# Runtime download configuration.
_define("DOWNLOAD_DIR", "string", ConfigCategory.RUNTIME, "/app/downloads", runtime_editable=True, worker_reload_required=True, description="Download directory", validator=_download_dir)
_define("TARGET_CHATS", "json", ConfigCategory.RUNTIME, [], runtime_editable=True, worker_reload_required=True, description="Telegram channels or groups", validator=_csv)
_define("ALLOW_EXTS", "json", ConfigCategory.RUNTIME, [".mp4", ".mkv", ".mov", ".avi", ".jpg", ".jpeg", ".png", ".webp"], runtime_editable=True, worker_reload_required=True, description="Allowed media extensions", validator=_extensions)
_define("DOWNLOAD_HISTORY", "boolean", ConfigCategory.RUNTIME, True, runtime_editable=True, worker_reload_required=True, description="Download historical messages", validator=_boolean)
_define("HISTORY_LIMIT", "integer", ConfigCategory.RUNTIME, 2000, runtime_editable=True, worker_reload_required=True, description="Maximum messages scanned per channel", validator=_bounded_integer(0, 100000))
_define("MAX_RETRIES", "integer", ConfigCategory.RUNTIME, 3, runtime_editable=True, worker_reload_required=True, description="Download retry count", validator=_bounded_integer(0, 20))
_define("RETRY_DELAY", "integer", ConfigCategory.RUNTIME, 5, runtime_editable=True, worker_reload_required=True, description="Retry delay in seconds", validator=_bounded_integer(0, 3600))
_define("MAX_FILE_SIZE_MB", "integer", ConfigCategory.RUNTIME, 0, runtime_editable=True, worker_reload_required=True, description="Maximum file size in MiB; zero disables the limit", validator=_bounded_integer(0, 1048576))


TELEGRAM_KEYS = ("API_ID", "API_HASH", "PHONE_NUMBER", "SESSION_NAME")
DOWNLOAD_KEYS = (
    "DOWNLOAD_DIR",
    "TARGET_CHATS",
    "ALLOW_EXTS",
    "DOWNLOAD_HISTORY",
    "HISTORY_LIMIT",
    "MAX_RETRIES",
    "RETRY_DELAY",
    "MAX_FILE_SIZE_MB",
)
DATABASE_KEYS = TELEGRAM_KEYS + DOWNLOAD_KEYS


def get_definition(key: str) -> ConfigDefinition:
    try:
        return CONFIG_REGISTRY[key]
    except KeyError as exc:
        raise AppException(f"unsupported setting key: {key}", status_code=400) from exc


def validate_config_value(key: str, value: Any) -> Any:
    definition = get_definition(key)
    try:
        return definition.validator(value)
    except (TypeError, ValueError) as exc:
        raise AppException(f"invalid value for {key}", status_code=422) from exc


def encode_storage_value(key: str, value: Any) -> str:
    definition = get_definition(key)
    if definition.value_type == "boolean":
        return "true" if bool(value) else "false"
    if definition.value_type == "json":
        if isinstance(value, list):
            return ",".join(str(item) for item in value)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def decode_storage_value(key: str, value: Any) -> Any:
    definition = get_definition(key)
    if value is None or str(value).strip() == "":
        return definition.default
    return validate_config_value(key, value)


def validate_update_batch(values: dict[str, Any], *, allow_secrets: bool) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, raw_value in values.items():
        definition = get_definition(key)
        if not definition.runtime_editable:
            raise AppException(f"setting is not runtime editable: {key}", status_code=400)
        if definition.secret and not allow_secrets:
            raise AppException(f"secret setting requires the dedicated API: {key}", status_code=403)
        validated = validate_config_value(key, raw_value)
        normalized[key] = encode_storage_value(key, validated)
    return normalized


def public_runtime_definitions() -> list[ConfigDefinition]:
    return [
        definition
        for definition in CONFIG_REGISTRY.values()
        if definition.runtime_editable and not definition.secret
    ]

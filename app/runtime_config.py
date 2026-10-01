import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Reuse the backend registry so the worker has no independent defaults.
_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.core.config_registry import (  # noqa: E402
    DATABASE_KEYS,
    decode_storage_value,
    encode_storage_value,
    get_definition,
)


def _default_app_home() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata and appdata.strip():
        return Path(os.path.expandvars(appdata)).expanduser() / "TelegramMediaApp"
    return Path.home() / "AppData" / "Roaming" / "TelegramMediaApp"


def _resolve_app_home() -> Path:
    raw = os.getenv("APP_HOME", "").strip()
    if raw:
        path = Path(os.path.expandvars(raw)).expanduser()
        if not path.is_absolute():
            path = (_default_app_home() / path).resolve()
        return path
    return _default_app_home()


def _load_env_file() -> Path:
    """Load optional env files without overriding process/Docker environment."""

    project_root_env = Path(__file__).resolve().parent.parent / ".env"
    if project_root_env.exists():
        load_dotenv(project_root_env, override=False)

    app_home = _resolve_app_home()
    runtime_env_path = Path(
        os.path.expandvars(os.getenv("RUNTIME_ENV_FILE", str(app_home / "config" / "runtime.env")))
    ).expanduser()
    if runtime_env_path.exists():
        load_dotenv(runtime_env_path, override=False)
    return _resolve_app_home()


def _load_settings_from_db() -> dict[str, str]:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("sqlite:///"):
        return {}
    db_file = Path(database_url.replace("sqlite:///", "", 1))
    if not db_file.exists():
        return {}

    try:
        with sqlite3.connect(db_file) as conn:
            placeholders = ",".join(["?"] * len(DATABASE_KEYS))
            rows = conn.execute(
                f"SELECT key, value FROM app_settings WHERE key IN ({placeholders})",
                DATABASE_KEYS,
            ).fetchall()
    except Exception:
        return {}
    return {str(key): "" if value is None else str(value) for key, value in rows}


def _default_raw(key: str) -> str:
    definition = get_definition(key)
    if definition.default in (None, ""):
        return ""
    return encode_storage_value(key, definition.default)


@dataclass(slots=True)
class RuntimeConfig:
    api_id: int
    api_hash: str
    phone_number: str
    session_name: str
    download_dir: str
    target_chats: list[str]
    allow_exts: list[str]
    download_history: bool
    history_limit: int
    max_retries: int
    retry_delay: int
    max_file_size_mb: int
    hash_index_file: str


def load_runtime_config() -> RuntimeConfig:
    _load_env_file()
    db_settings = _load_settings_from_db()

    def resolved(key: str):
        raw = db_settings.get(key)
        if raw is None or not raw.strip():
            raw = os.getenv(key, "")
        if raw is None or not str(raw).strip():
            raw = _default_raw(key)
        return decode_storage_value(key, raw)

    session_name = resolved("SESSION_NAME")
    download_dir = resolved("DOWNLOAD_DIR")
    hash_index_file = decode_storage_value(
        "HASH_INDEX_FILE",
        os.getenv("HASH_INDEX_FILE", _default_raw("HASH_INDEX_FILE")),
    )

    Path(session_name).parent.mkdir(parents=True, exist_ok=True)
    Path(download_dir).mkdir(parents=True, exist_ok=True)
    Path(hash_index_file).parent.mkdir(parents=True, exist_ok=True)

    return RuntimeConfig(
        api_id=resolved("API_ID"),
        api_hash=resolved("API_HASH"),
        phone_number=resolved("PHONE_NUMBER"),
        session_name=session_name,
        download_dir=download_dir,
        target_chats=resolved("TARGET_CHATS"),
        allow_exts=resolved("ALLOW_EXTS"),
        download_history=resolved("DOWNLOAD_HISTORY"),
        history_limit=resolved("HISTORY_LIMIT"),
        max_retries=resolved("MAX_RETRIES"),
        retry_delay=resolved("RETRY_DELAY"),
        max_file_size_mb=resolved("MAX_FILE_SIZE_MB"),
        hash_index_file=hash_index_file,
    )

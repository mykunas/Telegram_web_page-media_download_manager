import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


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
    """
    Load env files with desktop-first strategy:
    1) project root .env
    2) runtime env (RUNTIME_ENV_FILE or <APP_HOME>/config/runtime.env)
    """

    project_root_env = Path(__file__).resolve().parent.parent / ".env"
    if project_root_env.exists():
        load_dotenv(project_root_env, override=True)

    app_home = _resolve_app_home()
    runtime_env_path = Path(
        os.path.expandvars(os.getenv("RUNTIME_ENV_FILE", str(app_home / "config" / "runtime.env")))
    ).expanduser()
    if runtime_env_path.exists():
        load_dotenv(runtime_env_path, override=True)

    # Reload app_home because APP_HOME may be provided by .env/runtime.env.
    return _resolve_app_home()


def _load_settings_from_db() -> dict[str, str]:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("sqlite:///"):
        return {}

    db_path = database_url.replace("sqlite:///", "", 1)
    if not db_path:
        return {}

    db_file = Path(db_path)
    if not db_file.exists():
        return {}

    keys = (
        "API_ID",
        "API_HASH",
        "PHONE_NUMBER",
        "SESSION_NAME",
        "DOWNLOAD_DIR",
        "TARGET_CHATS",
        "ALLOW_EXTS",
        "DOWNLOAD_HISTORY",
        "HISTORY_LIMIT",
        "MAX_RETRIES",
        "RETRY_DELAY",
        "MAX_FILE_SIZE_MB",
        "HASH_INDEX_FILE",
    )

    try:
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        placeholders = ",".join(["?"] * len(keys))
        cur.execute(f"SELECT key, value FROM app_settings WHERE key IN ({placeholders})", keys)
        rows = cur.fetchall()
        conn.close()
    except Exception:
        return {}

    return {str(key): "" if value is None else str(value) for key, value in rows}


@dataclass(slots=True)
class RuntimeConfig:
    api_id: int
    api_hash: str
    phone_number: str | None
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


def _resolve_path(value: str, app_home: Path) -> Path:
    path = Path(os.path.expandvars(value)).expanduser()
    if path.is_absolute():
        return path
    return (app_home / path).resolve()


def load_runtime_config() -> RuntimeConfig:
    app_home = _load_env_file()
    app_home.mkdir(parents=True, exist_ok=True)

    db_settings = _load_settings_from_db()

    def _get(key: str, default: str) -> str:
        raw = db_settings.get(key)
        if raw is not None and str(raw).strip() != "":
            return str(raw)
        return os.getenv(key, default)

    session_name_path = _resolve_path(_get("SESSION_NAME", str(app_home / "session" / "telegram_user")), app_home)
    download_dir_path = _resolve_path(_get("DOWNLOAD_DIR", str(app_home / "downloads")), app_home)
    hash_index_file_path = _resolve_path(_get("HASH_INDEX_FILE", str(app_home / "data" / "hash_index.json")), app_home)

    session_name_path.parent.mkdir(parents=True, exist_ok=True)
    download_dir_path.mkdir(parents=True, exist_ok=True)
    hash_index_file_path.parent.mkdir(parents=True, exist_ok=True)

    return RuntimeConfig(
        api_id=int(_get("API_ID", "0")),
        api_hash=_get("API_HASH", ""),
        phone_number=_get("PHONE_NUMBER", ""),
        session_name=str(session_name_path),
        download_dir=str(download_dir_path),
        target_chats=[x.strip() for x in _get("TARGET_CHATS", "").split(",") if x.strip()],
        allow_exts=[x.lower().strip() for x in _get("ALLOW_EXTS", ".mp4,.jpg,.jpeg,.png,.webp").split(",") if x.strip()],
        download_history=_get("DOWNLOAD_HISTORY", "true").lower() == "true",
        history_limit=int(_get("HISTORY_LIMIT", "200")),
        max_retries=int(_get("MAX_RETRIES", "3")),
        retry_delay=int(_get("RETRY_DELAY", "5")),
        max_file_size_mb=int(_get("MAX_FILE_SIZE_MB", "0")),
        hash_index_file=str(hash_index_file_path),
    )

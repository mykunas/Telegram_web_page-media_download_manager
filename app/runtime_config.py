import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_env_file() -> None:
    """Load env from container path first, then project root as fallback."""

    container_env = Path("/app/.env")
    local_env = Path(__file__).resolve().parent.parent / ".env"

    if container_env.exists():
        load_dotenv(container_env, override=True)
    elif local_env.exists():
        load_dotenv(local_env, override=True)


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


def load_runtime_config() -> RuntimeConfig:
    _load_env_file()
    db_settings = _load_settings_from_db()

    def _get(key: str, default: str) -> str:
        raw = db_settings.get(key)
        if raw is not None and str(raw).strip() != "":
            return str(raw)
        return os.getenv(key, default)

    return RuntimeConfig(
        api_id=int(_get("API_ID", "0")),
        api_hash=_get("API_HASH", ""),
        phone_number=_get("PHONE_NUMBER", ""),
        session_name=_get("SESSION_NAME", "/app/session/telegram_user"),
        download_dir=_get("DOWNLOAD_DIR", "/downloads"),
        target_chats=[x.strip() for x in _get("TARGET_CHATS", "").split(",") if x.strip()],
        allow_exts=[x.lower().strip() for x in _get("ALLOW_EXTS", ".mp4,.jpg,.jpeg,.png,.webp").split(",") if x.strip()],
        download_history=_get("DOWNLOAD_HISTORY", "true").lower() == "true",
        history_limit=int(_get("HISTORY_LIMIT", "200")),
        max_retries=int(_get("MAX_RETRIES", "3")),
        retry_delay=int(_get("RETRY_DELAY", "5")),
        max_file_size_mb=int(_get("MAX_FILE_SIZE_MB", "0")),
        hash_index_file=os.getenv("HASH_INDEX_FILE", "/app/hash_index.json"),
    )

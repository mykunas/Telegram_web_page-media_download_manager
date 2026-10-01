from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bootstrap settings loaded from process environment and optional `.env`."""

    APP_NAME: str = "Telegram Media Downloader Backend"
    APP_VERSION: str = "0.3.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./data/app.db"
    LOG_LEVEL: str = "INFO"
    ALLOWED_HOSTS: str = "*"
    SESSION_DIR: str = "/app/session"
    DOWNLOAD_ROOT: str = "/app/downloads"
    ADMIN_AUTH_ENABLED: bool = False
    ADMIN_API_TOKEN_HASH: SecretStr = SecretStr("")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("invalid LOG_LEVEL")
        return normalized

    @field_validator("SESSION_DIR")
    @classmethod
    def validate_session_dir(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts or str(path) == path.anchor:
            raise ValueError("SESSION_DIR must be a safe absolute directory")
        return str(path)

    @field_validator("DOWNLOAD_ROOT")
    @classmethod
    def validate_download_root(cls, value: str) -> str:
        path = Path(value)
        if not path.is_absolute() or ".." in path.parts or str(path) == path.anchor:
            raise ValueError("DOWNLOAD_ROOT must be a safe absolute directory")
        return str(path)

    @model_validator(mode="after")
    def validate_admin_auth(self) -> "Settings":
        digest = self.ADMIN_API_TOKEN_HASH.get_secret_value().strip().lower()
        if digest and not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("ADMIN_API_TOKEN_HASH must be a SHA-256 hex digest")
        if self.ADMIN_AUTH_ENABLED and not digest:
            raise ValueError("ADMIN_API_TOKEN_HASH is required when ADMIN_AUTH_ENABLED=true")
        return self

    @property
    def allowed_hosts_list(self) -> list[str]:
        hosts = [item.strip() for item in self.ALLOWED_HOSTS.split(",") if item.strip()]
        return hosts or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

if settings.DATABASE_URL.startswith("sqlite:///"):
    db_path = settings.DATABASE_URL.replace("sqlite:///", "", 1)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

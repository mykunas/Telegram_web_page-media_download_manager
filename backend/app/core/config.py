from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    APP_NAME: str = "Telegram Media Downloader Backend"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    API_V1_PREFIX: str = "/api/v1"

    # SQLite default path: backend/data/app.db
    DATABASE_URL: str = "sqlite:///./data/app.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance to avoid repeated disk/env reads."""

    return Settings()


settings = get_settings()

# Ensure local SQLite directory exists when using default sqlite path.
if settings.DATABASE_URL.startswith("sqlite:///"):
    db_path = settings.DATABASE_URL.replace("sqlite:///", "", 1)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)


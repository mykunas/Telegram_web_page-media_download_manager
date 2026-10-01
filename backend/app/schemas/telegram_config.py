from __future__ import annotations

from pydantic import BaseModel, Field


class TelegramConfigPayload(BaseModel):
    API_ID: str | None = Field(default=None, max_length=20)
    API_HASH: str | None = Field(default=None, max_length=128)
    PHONE_NUMBER: str | None = Field(default=None, max_length=32)
    SESSION_NAME: str | None = Field(default=None, max_length=255)


class DownloadConfigPayload(BaseModel):
    DOWNLOAD_DIR: str = Field(default="/downloads")
    TARGET_CHATS: str = Field(default="")
    ALLOW_EXTS: str = Field(default="")
    DOWNLOAD_HISTORY: bool = Field(default=True)
    HISTORY_LIMIT: int = Field(default=2000)
    MAX_RETRIES: int = Field(default=3)
    RETRY_DELAY: int = Field(default=5)
    MAX_FILE_SIZE_MB: int = Field(default=0)


class CodeSubmitPayload(BaseModel):
    code: str = Field(min_length=1, max_length=20)


class PasswordSubmitPayload(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class SessionDeletePayload(BaseModel):
    confirm: str = Field(min_length=1, max_length=32)


class SecretClearPayload(BaseModel):
    confirm: str = Field(min_length=1, max_length=64)

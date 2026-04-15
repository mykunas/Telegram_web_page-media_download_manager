from __future__ import annotations

from pydantic import BaseModel, Field


class TelegramConfigPayload(BaseModel):
    API_ID: str = Field(default="")
    API_HASH: str = Field(default="")
    PHONE_NUMBER: str = Field(default="")
    SESSION_NAME: str = Field(default="")


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

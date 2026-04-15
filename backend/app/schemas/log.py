from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SystemLogOut(BaseModel):
    id: int
    level: str
    module: str
    message: str
    extra_json: dict | None
    created_at: datetime


class ErrorLogOut(BaseModel):
    id: int
    module: str
    chat_id: int | None
    message_id: int | None
    file_path: str | None
    error_type: str
    error_message: str
    traceback: str | None
    resolved: bool
    created_at: datetime


class ErrorResolveOut(BaseModel):
    id: int
    resolved: bool

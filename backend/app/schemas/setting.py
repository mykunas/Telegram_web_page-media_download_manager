from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SettingItemOut(BaseModel):
    id: int
    key: str
    value: str | None
    value_type: str
    description: str | None
    parsed_value: Any = None
    updated_at: datetime


class SettingUpdateItem(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: Any = None
    value_type: str | None = Field(default=None)
    description: str | None = Field(default=None, max_length=255)


class SettingBatchUpdateRequest(BaseModel):
    items: list[SettingUpdateItem] = Field(default_factory=list)


class SettingUpdateResult(BaseModel):
    updated_count: int
    created_count: int
    items: list[SettingItemOut]


class SettingReloadResult(BaseModel):
    reloaded_count: int
    reloaded_keys: list[str]

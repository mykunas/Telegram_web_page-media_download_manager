from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RandomPickRequest(BaseModel):
    media_type: str | None = Field(default=None, description="video/photo/document")
    min_size: int | None = Field(default=None, ge=0)
    max_size: int | None = Field(default=None, ge=0)
    duration_range: list[int] | None = Field(default=None, description="reserved for future")
    exclude_recent_minutes: int | None = Field(default=30, ge=0, le=1440)


class PlayProgressUpdateRequest(BaseModel):
    last_position_sec: float = Field(default=0.0, ge=0)
    duration_sec: float = Field(default=0.0, ge=0)
    is_completed: bool | None = None


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    sort_order: int | None = None


class CollectionUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    sort_order: int | None = None


class CollectionAddItemRequest(BaseModel):
    record_id: int = Field(ge=1)
    sort_order: int | None = None


class PreferenceManualItem(BaseModel):
    kind: Literal["channel", "media_type", "tag"]
    key: str = Field(min_length=1, max_length=255)
    weight: float = Field(ge=-5.0, le=5.0)


class PreferenceManualUpdateRequest(BaseModel):
    items: list[PreferenceManualItem] = Field(default_factory=list)


class PlaybackInitRequest(BaseModel):
    mode: Literal["sequential", "random"] = "sequential"
    slot_count: int = Field(default=8, ge=1, le=256)
    use_saved_state: bool = True


class PlaybackStateUpdateRequest(BaseModel):
    mode: Literal["sequential", "random"] = "sequential"
    queue_ids: list[int] = Field(default_factory=list)
    slots: list[dict] = Field(default_factory=list)
    stats: dict | None = None

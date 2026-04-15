from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DownloadRecordOut(BaseModel):
    id: int
    chat_id: int
    chat_name: str | None
    message_id: int
    message_date: datetime | None
    media_type: str | None
    original_file_name: str | None
    saved_file_name: str | None
    saved_path: str | None
    file_size: int | None
    sha256: str | None
    status: str
    source_type: str | None
    retry_count: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class DownloadListData(BaseModel):
    list: list[DownloadRecordOut]
    total: int
    page: int
    page_size: int


class BatchRetryRequest(BaseModel):
    ids: list[int] = Field(default_factory=list, description="DownloadRecord ids to retry")


class BatchRetryResult(BaseModel):
    retried_count: int
    retried_ids: list[int]

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SyncStatusOut(BaseModel):
    id: int
    chat_id: int
    last_scanned_message_id: int | None
    last_downloaded_message_id: int | None
    total_found: int
    total_success: int
    total_failed: int
    total_skipped: int
    missing_count: int
    sync_status: str
    last_sync_at: datetime | None


class SyncStatusListData(BaseModel):
    service: dict[str, Any]
    count: int
    channels: list[SyncStatusOut]


class SyncServiceActionResult(BaseModel):
    action: str
    accepted: bool
    service_running: bool
    history_task_running: bool
    recheck_task_running: bool
    detail: str | None = None


class SyncTaskTriggerResult(BaseModel):
    action: str
    accepted: bool
    detail: str | None = None

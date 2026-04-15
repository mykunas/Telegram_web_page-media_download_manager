from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend_db import DownloadStatus, SyncStatus, db_session_scope
from log_service import LogService


class SyncService:
    """Manage per-channel Telegram synchronization status."""

    def __init__(self, log_service: LogService) -> None:
        self.log_service = log_service

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def _get_or_create(self, db, chat_id: int) -> SyncStatus:
        row = db.query(SyncStatus).filter(SyncStatus.chat_id == chat_id).first()
        if row:
            return row

        row = SyncStatus(
            chat_id=chat_id,
            last_scanned_message_id=None,
            last_downloaded_message_id=None,
            total_found=0,
            total_success=0,
            total_failed=0,
            total_skipped=0,
            missing_count=0,
            sync_status="idle",
            last_sync_at=self._utcnow(),
        )
        db.add(row)
        db.flush()
        return row

    def _apply_update(self, chat_id: int, updater) -> bool:
        try:
            with db_session_scope() as db:
                row = self._get_or_create(db, chat_id)
                updater(row)
                row.last_sync_at = self._utcnow()
            return True
        except Exception as exc:
            self.log_service.log_error(
                module="sync_service",
                error_type=exc.__class__.__name__,
                error_message=f"Failed to update sync status for chat {chat_id}: {exc}",
                chat_id=chat_id,
            )
            return False

    def init_channel_status(self, chat_id: int, sync_status: str = "idle") -> bool:
        """Initialize channel sync status row if missing and set status."""

        return self._apply_update(chat_id, lambda row: setattr(row, "sync_status", sync_status))

    def set_sync_status(self, chat_id: int, sync_status: str) -> bool:
        """Set channel sync status (idle/running/completed/error)."""

        return self._apply_update(chat_id, lambda row: setattr(row, "sync_status", sync_status))

    def update_last_scanned_message_id(self, chat_id: int, message_id: int) -> bool:
        """Update latest scanned message id for a channel."""

        return self._apply_update(chat_id, lambda row: setattr(row, "last_scanned_message_id", message_id))

    def update_last_downloaded_message_id(self, chat_id: int, message_id: int) -> bool:
        """Update latest downloaded message id for a channel."""

        return self._apply_update(chat_id, lambda row: setattr(row, "last_downloaded_message_id", message_id))

    def increment_total_found(self, chat_id: int, amount: int = 1) -> bool:
        """Increase total found media count."""

        return self._apply_update(chat_id, lambda row: setattr(row, "total_found", row.total_found + amount))

    def increment_total_success(self, chat_id: int, amount: int = 1) -> bool:
        """Increase total successful download count."""

        return self._apply_update(chat_id, lambda row: setattr(row, "total_success", row.total_success + amount))

    def increment_total_failed(self, chat_id: int, amount: int = 1) -> bool:
        """Increase total failed download count."""

        return self._apply_update(chat_id, lambda row: setattr(row, "total_failed", row.total_failed + amount))

    def increment_total_skipped(self, chat_id: int, amount: int = 1) -> bool:
        """Increase total skipped/duplicate download count."""

        return self._apply_update(chat_id, lambda row: setattr(row, "total_skipped", row.total_skipped + amount))

    def update_sync_counters(
        self,
        chat_id: int,
        *,
        found: int = 0,
        success: int = 0,
        failed: int = 0,
        skipped: int = 0,
    ) -> bool:
        """Batch-update channel counters in a single transaction."""

        def _updater(row: SyncStatus) -> None:
            row.total_found += found
            row.total_success += success
            row.total_failed += failed
            row.total_skipped += skipped

        return self._apply_update(chat_id, _updater)

    def get_sync_status(self, chat_id: int) -> SyncStatus | None:
        """Get raw SyncStatus ORM object by chat_id."""

        try:
            with db_session_scope() as db:
                return db.query(SyncStatus).filter(SyncStatus.chat_id == chat_id).first()
        except Exception as exc:
            self.log_service.log_error(
                module="sync_service",
                error_type=exc.__class__.__name__,
                error_message=f"Failed to query sync status for chat {chat_id}: {exc}",
                chat_id=chat_id,
            )
            return None

    def get_sync_status_data(self, chat_id: int) -> dict[str, Any] | None:
        """Get sync status as dict for easy API response integration."""

        row = self.get_sync_status(chat_id)
        if not row:
            return None

        return {
            "id": row.id,
            "chat_id": row.chat_id,
            "last_scanned_message_id": row.last_scanned_message_id,
            "last_downloaded_message_id": row.last_downloaded_message_id,
            "total_found": row.total_found,
            "total_success": row.total_success,
            "total_failed": row.total_failed,
            "total_skipped": row.total_skipped,
            "missing_count": row.missing_count,
            "sync_status": row.sync_status,
            "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
        }

    # Backward-compatible wrappers for current downloader flow.
    def set_chat_sync_status(self, chat_id: int, status: str) -> None:
        self.set_sync_status(chat_id, status)

    def record_history_found(self, chat_id: int, message_id: int) -> None:
        self.update_last_scanned_message_id(chat_id, message_id)
        self.increment_total_found(chat_id)

    def record_download_result(self, chat_id: int, message_id: int, status: DownloadStatus) -> None:
        self.update_last_downloaded_message_id(chat_id, message_id)

        if status == DownloadStatus.SUCCESS:
            self.increment_total_success(chat_id)
        elif status == DownloadStatus.FAILED:
            self.increment_total_failed(chat_id)
        elif status in (DownloadStatus.SKIPPED, DownloadStatus.DUPLICATE):
            self.increment_total_skipped(chat_id)

    def mark_history_completed(self, chat_id: int) -> None:
        self.set_sync_status(chat_id, "completed")
        self.log_service.log_system("info", "sync_service", f"History scan completed for chat {chat_id}")

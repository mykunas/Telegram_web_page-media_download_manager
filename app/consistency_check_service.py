from __future__ import annotations

import os
import re
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from pyrogram import Client
from pyrogram.types import Message

from backend_db import DownloadRecord, DownloadStatus, SyncStatus, db_session_scope
from log_service import LogService
from runtime_config import RuntimeConfig
from sync_service import SyncService


@dataclass(slots=True)
class ConsistencyCheckResult:
    chat_id: int
    chat_ref: str
    checked_at: str
    telegram_media_count: int
    db_record_count: int
    local_media_count: int
    missing_count: int
    orphan_file_count: int
    broken_record_count: int


class ConsistencyCheckService:
    """Consistency checker among Telegram history, DB records and local files."""

    MESSAGE_KEY_PATTERN = re.compile(r"_(-?\d+)_(\d+)_")

    def __init__(
        self,
        client: Client,
        config: RuntimeConfig,
        log_service: LogService,
        sync_service: SyncService,
    ) -> None:
        self.client = client
        self.config = config
        self.log_service = log_service
        self.sync_service = sync_service

    @staticmethod
    def _is_media_message(message: Message) -> bool:
        return bool(message.video or message.photo or message.document)

    @staticmethod
    def _message_key(chat_id: int, message_id: int) -> str:
        return f"{chat_id}:{message_id}"

    def _extract_message_key_from_filename(self, filename: str) -> str | None:
        match = self.MESSAGE_KEY_PATTERN.search(filename)
        if not match:
            return None
        chat_id = int(match.group(1))
        message_id = int(match.group(2))
        return self._message_key(chat_id, message_id)

    async def _collect_telegram_keys(self, chat_ref: str, history_limit: int) -> tuple[int, set[str], list[str]]:
        telegram_keys: set[str] = set()
        raw_keys: list[str] = []

        async for message in self.client.get_chat_history(chat_ref, limit=history_limit):
            if not self._is_media_message(message):
                continue
            key = self._message_key(int(message.chat.id), int(message.id))
            telegram_keys.add(key)
            raw_keys.append(key)

        return len(raw_keys), telegram_keys, raw_keys

    def _collect_db_records(self, chat_id: int) -> list[DownloadRecord]:
        with db_session_scope() as db:
            rows = db.query(DownloadRecord).filter(DownloadRecord.chat_id == chat_id).all()
            for row in rows:
                db.expunge(row)
            return rows

    def _collect_local_file_keys(self, target_chat_id: int) -> tuple[int, set[str]]:
        local_keys: set[str] = set()
        file_count = 0

        for root, _, files in os.walk(self.config.download_dir):
            for filename in files:
                if filename.endswith(".part"):
                    continue
                file_count += 1
                key = self._extract_message_key_from_filename(filename)
                if not key:
                    continue
                chat_id_str, _ = key.split(":", 1)
                if int(chat_id_str) != target_chat_id:
                    continue
                local_keys.add(key)

        return file_count, local_keys

    def _classify_broken_records(self, rows: list[DownloadRecord]) -> tuple[int, list[str]]:
        broken_keys: list[str] = []
        stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)

        for row in rows:
            key = self._message_key(int(row.chat_id), int(row.message_id))

            if row.status in (DownloadStatus.SUCCESS, DownloadStatus.DUPLICATE):
                if not row.saved_path or not os.path.exists(row.saved_path):
                    broken_keys.append(key)
                    continue

            if row.status == DownloadStatus.SUCCESS and (not row.sha256 or not row.saved_file_name):
                broken_keys.append(key)
                continue

            if row.status == DownloadStatus.FAILED and not row.error_message:
                broken_keys.append(key)
                continue

            if row.status in (DownloadStatus.WAITING, DownloadStatus.DOWNLOADING):
                created_at = row.created_at
                if created_at is not None:
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    if created_at < stale_threshold:
                        broken_keys.append(key)

        return len(set(broken_keys)), sorted(set(broken_keys))

    def _update_sync_missing_count(self, chat_id: int, missing_count: int) -> None:
        # Keep this update close to SyncStatus semantics and available for API reads.
        with db_session_scope() as db:
            row = db.query(SyncStatus).filter(SyncStatus.chat_id == chat_id).first()
            if row is None:
                row = SyncStatus(
                    chat_id=chat_id,
                    last_scanned_message_id=None,
                    last_downloaded_message_id=None,
                    total_found=0,
                    total_success=0,
                    total_failed=0,
                    total_skipped=0,
                    missing_count=missing_count,
                    sync_status="idle",
                    last_sync_at=datetime.now(timezone.utc),
                )
                db.add(row)
            else:
                row.missing_count = missing_count
                row.last_sync_at = datetime.now(timezone.utc)

    def _log_issue_keys(self, issue_name: str, chat_id: int, keys: list[str], max_items: int = 20) -> None:
        if not keys:
            return

        shown = keys[:max_items]
        self.log_service.log_system(
            "warning",
            "consistency_check",
            f"{issue_name} detected for chat {chat_id}: {len(keys)}",
            extra_json={
                "chat_id": chat_id,
                "issue": issue_name,
                "count": len(keys),
                "sample_keys": shown,
            },
        )

    async def check_channel(self, chat_ref: str, history_limit: int | None = None) -> ConsistencyCheckResult:
        history_limit = history_limit or self.config.history_limit

        try:
            chat = await self.client.get_chat(chat_ref)
            chat_id = int(chat.id)

            self.log_service.log_system(
                "info",
                "consistency_check",
                f"Start consistency check for {chat_ref}",
                extra_json={"chat_id": chat_id, "history_limit": history_limit},
            )

            telegram_count, telegram_keys, _ = await self._collect_telegram_keys(chat_ref, history_limit)

            db_rows = self._collect_db_records(chat_id)
            db_keys = {self._message_key(int(row.chat_id), int(row.message_id)) for row in db_rows}

            local_count, local_keys = self._collect_local_file_keys(chat_id)

            missing_keys = sorted(telegram_keys - db_keys)
            orphan_keys = sorted(local_keys - db_keys)
            broken_count, broken_keys = self._classify_broken_records(db_rows)

            self._log_issue_keys("missing_download_record", chat_id, missing_keys)
            self._log_issue_keys("orphan_local_file", chat_id, orphan_keys)
            self._log_issue_keys("broken_download_record", chat_id, broken_keys)

            self._update_sync_missing_count(chat_id, len(missing_keys))

            result = ConsistencyCheckResult(
                chat_id=chat_id,
                chat_ref=chat_ref,
                checked_at=datetime.now(timezone.utc).isoformat(),
                telegram_media_count=telegram_count,
                db_record_count=len(db_rows),
                local_media_count=local_count,
                missing_count=len(missing_keys),
                orphan_file_count=len(orphan_keys),
                broken_record_count=broken_count,
            )

            self.log_service.log_system(
                "info",
                "consistency_check",
                f"Consistency check completed for {chat_ref}",
                extra_json=asdict(result),
            )

            return result

        except Exception as exc:
            self.log_service.log_error(
                module="consistency_check",
                error_type=exc.__class__.__name__,
                error_message=f"Consistency check failed for {chat_ref}: {exc}",
                traceback_text=traceback.format_exc(),
            )
            raise

    async def check_all_channels(self, history_limit: int | None = None) -> list[ConsistencyCheckResult]:
        """Service method entrypoint for API/task layer to invoke consistency checks."""

        results: list[ConsistencyCheckResult] = []
        for chat_ref in self.config.target_chats:
            result = await self.check_channel(chat_ref, history_limit=history_limit)
            results.append(result)

        return results

import asyncio
import hashlib
import json
import os
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Awaitable, Callable, TypeVar

from pyrogram.types import Message

from backend_db import DownloadRecord, DownloadStatus, db_session_scope
from log_service import LogService
from runtime_config import RuntimeConfig
from sync_service import SyncService

T = TypeVar("T")


class DownloadService:
    def __init__(self, config: RuntimeConfig, log_service: LogService, sync_service: SyncService) -> None:
        self.config = config
        self.log_service = log_service
        self.sync_service = sync_service

        self.download_queue: asyncio.Queue[tuple[Message, str]] = asyncio.Queue()
        self.queued_keys: set[str] = set()
        self.fetch_message_by_ids: Callable[[int, int], Awaitable[Message | None]] | None = None

        self.hash_lock = Lock()
        self.hash_index = self.load_hash_index()

        Path(self.config.download_dir).mkdir(parents=True, exist_ok=True)

    def start_worker(self) -> None:
        self.recover_stale_downloading_records()
        asyncio.create_task(self.worker())
        asyncio.create_task(self.waiting_record_poller())
        self.log_service.log_system("info", "download_service", "Download worker started")

    def set_message_fetcher(self, fetcher: Callable[[int, int], Awaitable[Message | None]]) -> None:
        self.fetch_message_by_ids = fetcher
        self.log_service.log_system("info", "download_service", "Message fetcher registered")

    def recover_stale_downloading_records(self) -> int:
        """Move stale DOWNLOADING records back to WAITING after worker restart."""

        def _op() -> int:
            with db_session_scope() as db:
                rows = db.query(DownloadRecord).filter(DownloadRecord.status == DownloadStatus.DOWNLOADING).all()
                recovered = 0
                for row in rows:
                    row.status = DownloadStatus.WAITING
                    row.updated_at = datetime.now(timezone.utc)
                    row.error_message = "worker重启后自动恢复排队"
                    recovered += 1
                return recovered

        recovered_count = self._run_db_operation("recover_stale_downloading_records", _op, 0)
        if recovered_count > 0:
            self.log_service.log_system(
                "info",
                "download_service",
                f"Recovered stale downloading records: {recovered_count}",
            )
        return recovered_count

    def _truncate_utf8_bytes(self, text: str, max_bytes: int) -> str:
        if max_bytes <= 0:
            return ""
        data = text.encode("utf-8")
        if len(data) <= max_bytes:
            return text
        clipped = data[:max_bytes]
        while clipped and (clipped[-1] & 0xC0) == 0x80:
            clipped = clipped[:-1]
        result = clipped.decode("utf-8", errors="ignore").strip()
        return result or "file"

    def _fit_filename_bytes(self, filename: str, max_bytes: int = 220) -> str:
        filename = filename.strip() or "unnamed"
        stem, ext = os.path.splitext(filename)
        ext_bytes = len(ext.encode("utf-8"))
        stem_budget = max(1, max_bytes - ext_bytes)
        safe_stem = self._truncate_utf8_bytes(stem, stem_budget)
        candidate = f"{safe_stem}{ext}"
        if len(candidate.encode("utf-8")) <= max_bytes:
            return candidate
        return self._truncate_utf8_bytes(candidate, max_bytes)

    def safe_name(self, name: str) -> str:
        name = name.strip()
        name = re.sub(r'[\\/:*?"<>|]+', "_", name)
        name = re.sub(r"\s+", " ", name)
        if not name:
            return "unnamed"
        return self._fit_filename_bytes(name, max_bytes=140)

    def allowed(self, filename: str) -> bool:
        return any(filename.lower().endswith(ext) for ext in self.config.allow_exts)

    def get_chat_name(self, message: Message) -> str:
        return self.safe_name(message.chat.title or message.chat.username or str(message.chat.id))

    def get_date_parts(self, message: Message) -> tuple[str, str, str]:
        dt = message.date
        return dt.strftime("%Y-%m"), dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m-%d_%H-%M-%S")

    def get_media_size(self, message: Message) -> int:
        if message.video and getattr(message.video, "file_size", None):
            return int(message.video.file_size)
        if message.document and getattr(message.document, "file_size", None):
            return int(message.document.file_size)
        if message.photo and getattr(message.photo, "file_size", None):
            return int(message.photo.file_size)
        return 0

    def should_skip_by_size(self, message: Message) -> bool:
        if self.config.max_file_size_mb <= 0:
            return False
        size = self.get_media_size(message)
        return size > self.config.max_file_size_mb * 1024 * 1024

    def detect_media_type(self, message: Message) -> str | None:
        if message.video:
            return "video"
        if message.photo:
            return "photo"
        if message.document:
            return "document"
        return None

    def get_original_file_name(self, message: Message) -> str | None:
        if message.video:
            return getattr(message.video, "file_name", None) or f"{message.id}.mp4"
        if message.photo:
            return f"{message.id}_photo.jpg"
        if message.document:
            return getattr(message.document, "file_name", None) or f"{message.id}.bin"
        return None

    def build_target_path(self, message: Message) -> str | None:
        chat_name = self.get_chat_name(message)
        month_str, day_str, time_str = self.get_date_parts(message)

        if message.video:
            original_name = getattr(message.video, "file_name", None) or f"{message.id}.mp4"
            original_name = self.safe_name(original_name)
            filename = f"{time_str}_{message.chat.id}_{message.id}_{original_name}"
            filename = self._fit_filename_bytes(filename, max_bytes=220)
            sub_dir = "videos"
        elif message.photo:
            filename = f"{time_str}_{message.chat.id}_{message.id}_photo.jpg"
            filename = self._fit_filename_bytes(filename, max_bytes=220)
            sub_dir = "photos"
        elif message.document:
            original_name = getattr(message.document, "file_name", None) or f"{message.id}.bin"
            original_name = self.safe_name(original_name)
            filename = f"{time_str}_{message.chat.id}_{message.id}_{original_name}"
            filename = self._fit_filename_bytes(filename, max_bytes=220)
            sub_dir = "files"
        else:
            return None

        if not self.allowed(filename):
            return None

        target_dir = os.path.join(self.config.download_dir, chat_name, sub_dir, month_str, day_str)
        os.makedirs(target_dir, exist_ok=True)

        return os.path.join(target_dir, filename)

    def message_key(self, message: Message) -> str:
        return f"{message.chat.id}:{message.id}"

    def _message_ids(self, message: Message) -> tuple[int, int]:
        return int(message.chat.id), int(message.id)

    def list_waiting_records(self, limit: int = 100) -> list[tuple[int, int, str, int]]:
        def _op() -> list[tuple[int, int, str, int]]:
            with db_session_scope() as db:
                rows = (
                    db.query(DownloadRecord)
                    .filter(DownloadRecord.status == DownloadStatus.WAITING)
                    .order_by(DownloadRecord.created_at.asc(), DownloadRecord.id.asc())
                    .limit(limit)
                    .all()
                )
                return [
                    (
                        int(row.chat_id),
                        int(row.message_id),
                        str(row.source_type or "manual"),
                        int(row.retry_count or 0),
                    )
                    for row in rows
                ]

        return self._run_db_operation("list_waiting_records", _op, [])

    def _run_db_operation(self, operation_name: str, operation: Callable[[], T], default: T) -> T:
        """Execute DB operation with rollback support from db_session_scope and local exception guard."""

        try:
            return operation()
        except Exception as exc:
            print(f"[DB ERROR] {operation_name}: {exc}")
            self.log_service.log_system(
                "error",
                "download_service",
                f"Database operation failed: {operation_name}",
                extra_json={"error": str(exc)},
            )
            return default

    def load_hash_index(self) -> dict[str, str]:
        if not os.path.exists(self.config.hash_index_file):
            return {}
        try:
            with open(self.config.hash_index_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {str(k): str(v) for k, v in data.items()}
        except Exception:
            pass
        return {}

    def save_hash_index(self) -> None:
        with open(self.config.hash_index_file, "w", encoding="utf-8") as f:
            json.dump(self.hash_index, f, ensure_ascii=False, indent=2)

    def calc_file_sha256(self, path: str, chunk_size: int = 1024 * 1024) -> str:
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sha256.update(chunk)
        return sha256.hexdigest()

    def has_download_record(self, chat_id: int, message_id: int) -> bool:
        """Check whether a DownloadRecord already exists for (chat_id, message_id)."""

        def _op() -> bool:
            with db_session_scope() as db:
                existed = (
                    db.query(DownloadRecord)
                    .filter(DownloadRecord.chat_id == chat_id, DownloadRecord.message_id == message_id)
                    .first()
                )
                return existed is not None

        return self._run_db_operation("has_download_record", _op, False)

    def create_waiting_download_record(self, message: Message, source_type: str) -> bool:
        """Create DownloadRecord with waiting status before enqueue/download."""

        chat_id, message_id = self._message_ids(message)

        def _op() -> bool:
            with db_session_scope() as db:
                existed = (
                    db.query(DownloadRecord)
                    .filter(DownloadRecord.chat_id == chat_id, DownloadRecord.message_id == message_id)
                    .first()
                )
                if existed:
                    return False

                db.add(
                    DownloadRecord(
                        chat_id=chat_id,
                        chat_name=self.get_chat_name(message),
                        message_id=message_id,
                        message_date=message.date,
                        media_type=self.detect_media_type(message),
                        original_file_name=self.get_original_file_name(message),
                        saved_file_name=None,
                        saved_path=None,
                        file_size=self.get_media_size(message) or None,
                        sha256=None,
                        status=DownloadStatus.WAITING,
                        source_type=source_type,
                        retry_count=0,
                        error_message=None,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        completed_at=None,
                    )
                )
            return True

        return self._run_db_operation("create_waiting_download_record", _op, False)

    def _update_download_record_fields(self, message: Message, **fields) -> bool:
        """Update DownloadRecord by (chat_id, message_id)."""

        chat_id, message_id = self._message_ids(message)

        def _op() -> bool:
            with db_session_scope() as db:
                row = (
                    db.query(DownloadRecord)
                    .filter(DownloadRecord.chat_id == chat_id, DownloadRecord.message_id == message_id)
                    .first()
                )
                if not row:
                    return False

                for key, value in fields.items():
                    setattr(row, key, value)

                row.updated_at = datetime.now(timezone.utc)
            return True

        return self._run_db_operation("update_download_record_fields", _op, False)

    def mark_downloading(
        self,
        message: Message,
        source_type: str,
        retry_count: int,
        *,
        part_path: str | None = None,
        file_name: str | None = None,
        file_size: int | None = None,
    ) -> None:
        self._update_download_record_fields(
            message,
            status=DownloadStatus.DOWNLOADING,
            source_type=source_type,
            retry_count=retry_count,
            error_message=None,
            saved_path=part_path,
            saved_file_name=file_name,
            file_size=file_size,
        )

    def mark_download_success(self, message: Message, saved_path: str, file_size: int, sha256: str, retry_count: int) -> None:
        self._update_download_record_fields(
            message,
            status=DownloadStatus.SUCCESS,
            saved_path=saved_path,
            saved_file_name=os.path.basename(saved_path),
            file_size=file_size,
            sha256=sha256,
            retry_count=retry_count,
            error_message=None,
            completed_at=datetime.now(timezone.utc),
        )

    def mark_download_duplicate(self, message: Message, existing_path: str, file_size: int, sha256: str, retry_count: int) -> None:
        self._update_download_record_fields(
            message,
            status=DownloadStatus.DUPLICATE,
            saved_path=existing_path,
            saved_file_name=os.path.basename(existing_path),
            file_size=file_size,
            sha256=sha256,
            retry_count=retry_count,
            error_message="duplicate by sha256",
            completed_at=datetime.now(timezone.utc),
        )

    def mark_download_skipped(self, message: Message, reason: str) -> None:
        self._update_download_record_fields(
            message,
            status=DownloadStatus.SKIPPED,
            error_message=reason,
        )

    def mark_download_failed(self, message: Message, retry_count: int, error_message: str) -> None:
        self._update_download_record_fields(
            message,
            status=DownloadStatus.FAILED,
            retry_count=retry_count,
            error_message=error_message,
            completed_at=datetime.now(timezone.utc),
        )

    async def enqueue_message(self, message: Message, source_type: str) -> None:
        key = self.message_key(message)

        if key in self.queued_keys:
            self.log_service.log_system("info", "download_service", f"Skip already queued message {key}")
            return

        created = self.create_waiting_download_record(message, source_type)
        if not created:
            self.log_service.log_system(
                "info",
                "download_service",
                f"Skip duplicate message record {key}",
                extra_json={"source_type": source_type},
            )
            return

        self.queued_keys.add(key)
        await self.download_queue.put((message, source_type))
        self.log_service.log_system("info", "download_service", f"Enqueued {key}", {"source_type": source_type})

    async def enqueue_existing_record(self, message: Message, source_type: str) -> None:
        key = self.message_key(message)
        if key in self.queued_keys:
            return
        self.queued_keys.add(key)
        await self.download_queue.put((message, source_type))
        self.log_service.log_system("info", "download_service", f"Enqueued existing waiting record {key}")

    async def worker(self) -> None:
        while True:
            message, source_type = await self.download_queue.get()
            key = self.message_key(message)
            try:
                await self.download_with_retry(message, source_type)
            finally:
                self.queued_keys.discard(key)
                self.download_queue.task_done()

    def mark_waiting_record_failed(self, chat_id: int, message_id: int, error_message: str) -> None:
        def _op() -> bool:
            with db_session_scope() as db:
                row = (
                    db.query(DownloadRecord)
                    .filter(DownloadRecord.chat_id == chat_id, DownloadRecord.message_id == message_id)
                    .first()
                )
                if not row:
                    return False
                row.status = DownloadStatus.FAILED
                row.error_message = error_message
                row.completed_at = datetime.now(timezone.utc)
                row.updated_at = datetime.now(timezone.utc)
            return True

        self._run_db_operation("mark_waiting_record_failed", _op, False)

    def increment_waiting_record_retry(self, chat_id: int, message_id: int, error_message: str) -> bool:
        def _op() -> bool:
            with db_session_scope() as db:
                row = (
                    db.query(DownloadRecord)
                    .filter(DownloadRecord.chat_id == chat_id, DownloadRecord.message_id == message_id)
                    .first()
                )
                if not row or row.status != DownloadStatus.WAITING:
                    return False
                row.retry_count = int(row.retry_count or 0) + 1
                row.error_message = error_message
                row.updated_at = datetime.now(timezone.utc)
            return True

        return self._run_db_operation("increment_waiting_record_retry", _op, False)

    async def waiting_record_poller(self) -> None:
        while True:
            try:
                if self.fetch_message_by_ids is None:
                    await asyncio.sleep(5)
                    continue

                waiting_rows = self.list_waiting_records(limit=100)
                for chat_id, message_id, source_type, retry_count in waiting_rows:
                    key = f"{chat_id}:{message_id}"
                    if key in self.queued_keys:
                        continue

                    message = await self.fetch_message_by_ids(chat_id, message_id)
                    if not message:
                        next_retry_count = int(retry_count) + 1
                        if next_retry_count >= self.config.max_retries:
                            self.mark_waiting_record_failed(chat_id, message_id, "无法从 Telegram 拉取消息，请检查会话和系统时间")
                        else:
                            self.increment_waiting_record_retry(
                                chat_id,
                                message_id,
                                f"拉取消息失败，稍后自动重试 ({next_retry_count}/{self.config.max_retries})",
                            )
                        continue

                    await self.enqueue_existing_record(message, source_type)
            except Exception as exc:
                self.log_service.log_system(
                    "warning",
                    "download_service",
                    f"waiting_record_poller error: {exc}",
                )
            finally:
                await asyncio.sleep(5)

    async def _mark_skipped(self, message: Message, reason: str) -> None:
        self.mark_download_skipped(message, reason)
        self.sync_service.record_download_result(int(message.chat.id), int(message.id), DownloadStatus.SKIPPED)
        self.log_service.log_system("info", "download_service", f"Skipped {self.message_key(message)}: {reason}")

    async def download_with_retry(self, message: Message, source_type: str) -> None:
        final_path = self.build_target_path(message)
        if not final_path:
            await self._mark_skipped(message, "unsupported media or extension not allowed")
            return

        if self.should_skip_by_size(message):
            await self._mark_skipped(message, "exceeds MAX_FILE_SIZE_MB")
            return

        part_path = final_path + ".part"

        if os.path.exists(final_path):
            await self._mark_skipped(message, "target file already exists")
            return

        for attempt in range(1, self.config.max_retries + 1):
            try:
                if os.path.exists(part_path):
                    os.remove(part_path)

                self.mark_downloading(
                    message,
                    source_type=source_type,
                    retry_count=attempt - 1,
                    part_path=part_path,
                    file_name=os.path.basename(final_path),
                    file_size=self.get_media_size(message) or None,
                )

                self.log_service.log_system(
                    "info",
                    "download_service",
                    f"Try {attempt}/{self.config.max_retries} downloading {final_path}",
                )

                await message.download(file_name=part_path)

                if not os.path.exists(part_path):
                    raise RuntimeError("Temporary file not generated after download")

                size = os.path.getsize(part_path)
                if size == 0:
                    raise RuntimeError("Downloaded file size is 0 bytes")

                file_hash = self.calc_file_sha256(part_path)

                with self.hash_lock:
                    existing_path = self.hash_index.get(file_hash)

                    if existing_path and os.path.exists(existing_path):
                        os.remove(part_path)
                        self.mark_download_duplicate(
                            message,
                            existing_path=existing_path,
                            file_size=size,
                            sha256=file_hash,
                            retry_count=attempt - 1,
                        )
                        self.sync_service.record_download_result(
                            int(message.chat.id), int(message.id), DownloadStatus.DUPLICATE
                        )
                        self.log_service.log_system(
                            "info",
                            "download_service",
                            f"Duplicate file {final_path} -> {existing_path}",
                        )
                        return

                    os.replace(part_path, final_path)
                    self.hash_index[file_hash] = final_path
                    self.save_hash_index()

                self.mark_download_success(
                    message,
                    saved_path=final_path,
                    file_size=size,
                    sha256=file_hash,
                    retry_count=attempt - 1,
                )
                self.sync_service.record_download_result(int(message.chat.id), int(message.id), DownloadStatus.SUCCESS)
                self.log_service.log_system(
                    "info",
                    "download_service",
                    f"Downloaded {final_path} ({size} bytes, sha256={file_hash[:12]})",
                )
                return

            except Exception as exc:
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except Exception:
                        pass

                self.log_service.log_system(
                    "warning",
                    "download_service",
                    f"Download attempt {attempt} failed for {self.message_key(message)}: {exc}",
                )

                if attempt < self.config.max_retries:
                    await asyncio.sleep(self.config.retry_delay)
                    continue

                self.mark_download_failed(
                    message,
                    retry_count=attempt,
                    error_message=str(exc),
                )
                self.sync_service.record_download_result(int(message.chat.id), int(message.id), DownloadStatus.FAILED)
                self.log_service.log_error(
                    module="download_service",
                    chat_id=int(message.chat.id),
                    message_id=int(message.id),
                    file_path=final_path,
                    error_type=exc.__class__.__name__,
                    error_message=str(exc),
                    traceback_text=traceback.format_exc(),
                )
                return

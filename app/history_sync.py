from __future__ import annotations

import traceback
from collections.abc import Awaitable, Callable

from pyrogram import Client
from pyrogram.types import Message

from log_service import LogService
from sync_service import SyncService


class HistorySyncTask:
    """Scan Telegram chat history and enqueue unseen media messages for download."""

    def __init__(
        self,
        client: Client,
        target_chats: list[str],
        history_limit: int,
        enqueue_media_message: Callable[[Message, str], Awaitable[None]],
        has_message_record: Callable[[int, int], bool],
        sync_service: SyncService,
        log_service: LogService,
    ) -> None:
        self.client = client
        self.target_chats = target_chats
        self.history_limit = history_limit
        self.enqueue_media_message = enqueue_media_message
        self.has_message_record = has_message_record
        self.sync_service = sync_service
        self.log_service = log_service

    @staticmethod
    def _is_media_message(message: Message) -> bool:
        return bool(message.video or message.photo or message.document)

    @staticmethod
    def _parse_chat_id_hint(chat_ref: str) -> int | None:
        try:
            return int(str(chat_ref).strip())
        except Exception:
            return None

    async def scan_chat_history(self, chat_ref: str) -> dict[str, int]:
        found_count = 0
        enqueued_count = 0
        existed_count = 0
        chat_id = self._parse_chat_id_hint(chat_ref)

        try:
            chat = await self.client.get_chat(chat_ref)
            chat_id = int(chat.id)

            self.sync_service.set_chat_sync_status(chat_id, "running")
            self.log_service.log_system(
                "info",
                "history_sync",
                f"Start scanning history for {chat_ref}",
                extra_json={"chat_id": chat_id, "history_limit": self.history_limit},
            )

            async for message in self.client.get_chat_history(chat_ref, limit=self.history_limit):
                if not self._is_media_message(message):
                    continue

                msg_chat_id = int(message.chat.id)
                msg_id = int(message.id)
                found_count += 1

                # SyncStatus: maintain scan counters and latest scanned message id.
                self.sync_service.record_history_found(msg_chat_id, msg_id)

                if self.has_message_record(msg_chat_id, msg_id):
                    existed_count += 1
                    continue

                await self.enqueue_media_message(message, "history")
                enqueued_count += 1

            self.sync_service.mark_history_completed(chat_id)
            self.log_service.log_system(
                "info",
                "history_sync",
                f"History scan completed for {chat_ref}",
                extra_json={
                    "chat_id": chat_id,
                    "total_found": found_count,
                    "new_enqueued": enqueued_count,
                    "already_exists": existed_count,
                },
            )

            return {
                "chat_id": chat_id,
                "total_found": found_count,
                "new_enqueued": enqueued_count,
                "already_exists": existed_count,
            }

        except Exception as exc:
            if chat_id is not None:
                self.sync_service.set_chat_sync_status(chat_id, "error")
            self.log_service.log_error(
                module="history_sync",
                chat_id=chat_id if chat_id is not None else 0,
                error_type=exc.__class__.__name__,
                error_message=f"History scan failed for {chat_ref}: {exc}",
                traceback_text=traceback.format_exc(),
            )
            return {
                "chat_id": chat_id if chat_id is not None else 0,
                "total_found": found_count,
                "new_enqueued": enqueued_count,
                "already_exists": existed_count,
            }

    async def run(self) -> list[dict[str, int]]:
        """Run history scan for all configured chats."""

        results: list[dict[str, int]] = []
        for chat_ref in self.target_chats:
            result = await self.scan_chat_history(chat_ref)
            results.append(result)

        return results

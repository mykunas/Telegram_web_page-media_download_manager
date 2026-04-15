from __future__ import annotations

import traceback
from collections.abc import Awaitable, Callable

from pyrogram.types import Message

from log_service import LogService
from sync_service import SyncService


class RealtimeListener:
    """Handle real-time Telegram media messages and route them into download flow."""

    def __init__(
        self,
        enqueue_media_message: Callable[[Message, str], Awaitable[None]],
        has_message_record: Callable[[int, int], bool],
        sync_service: SyncService,
        log_service: LogService,
    ) -> None:
        self.enqueue_media_message = enqueue_media_message
        self.has_message_record = has_message_record
        self.sync_service = sync_service
        self.log_service = log_service

    @staticmethod
    def _is_media_message(message: Message) -> bool:
        return bool(message.video or message.photo or message.document)

    async def handle_message(self, message: Message) -> bool:
        """Process a live message. Return True when new message was queued for download."""

        chat_id = int(message.chat.id)
        message_id = int(message.id)
        key = f"{chat_id}:{message_id}"

        try:
            if not self._is_media_message(message):
                self.log_service.log_system("info", "realtime_listener", f"Skip non-media message {key}")
                return False

            if self.has_message_record(chat_id, message_id):
                self.log_service.log_system("info", "realtime_listener", f"Skip existing message {key}")
                return False

            await self.enqueue_media_message(message, "live")
            self.sync_service.update_last_downloaded_message_id(chat_id, message_id)

            self.log_service.log_system(
                "info",
                "realtime_listener",
                f"Queued live media message {key}",
                extra_json={"source_type": "live"},
            )
            return True

        except Exception as exc:
            self.log_service.log_error(
                module="realtime_listener",
                chat_id=chat_id,
                message_id=message_id,
                error_type=exc.__class__.__name__,
                error_message=f"Failed to process live message {key}: {exc}",
                traceback_text=traceback.format_exc(),
            )
            return False

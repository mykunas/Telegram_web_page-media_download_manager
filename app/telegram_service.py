import asyncio
from collections.abc import Awaitable, Callable

from pyrogram import Client, filters
from pyrogram.types import Message

from history_sync import HistorySyncTask
from log_service import LogService
from realtime_listener import RealtimeListener
from runtime_config import RuntimeConfig
from sync_service import SyncService


class TelegramService:
    def __init__(
        self,
        config: RuntimeConfig,
        log_service: LogService,
        sync_service: SyncService,
        on_media_message: Callable[[Message, str], Awaitable[None]],
        has_message_record: Callable[[int, int], bool],
    ) -> None:
        self.config = config
        self.log_service = log_service
        self.sync_service = sync_service
        self.on_media_message = on_media_message

        self.client = Client(
            name=self.config.session_name,
            api_id=self.config.api_id,
            api_hash=self.config.api_hash,
            phone_number=self.config.phone_number,
        )

        # Reuse the same download_service pipeline for both history and realtime.
        self.history_task = HistorySyncTask(
            client=self.client,
            target_chats=self.config.target_chats,
            history_limit=self.config.history_limit,
            enqueue_media_message=self.on_media_message,
            has_message_record=has_message_record,
            sync_service=self.sync_service,
            log_service=self.log_service,
        )

        self.realtime_listener = RealtimeListener(
            enqueue_media_message=self.on_media_message,
            has_message_record=has_message_record,
            sync_service=self.sync_service,
            log_service=self.log_service,
        )

        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.client.on_message(filters.chat(self.config.target_chats) & (filters.video | filters.photo | filters.document))
        async def handler(_, message: Message):
            await self.realtime_listener.handle_message(message)

    async def start(self) -> None:
        await self.client.start()
        me = await self.client.get_me()
        self.log_service.log_system(
            "info",
            "telegram_service",
            f"Telegram client started as {me.first_name} ({me.id})",
        )

    async def download_history(self) -> None:
        if not self.config.download_history:
            self.log_service.log_system("info", "telegram_service", "History download disabled")
            return

        # Network to Telegram may be temporarily unstable; retry instead of crashing worker.
        attempts = max(3, self.config.max_retries)
        for attempt in range(1, attempts + 1):
            try:
                await self.history_task.run()
                return
            except Exception as exc:
                self.log_service.log_system(
                    "warning",
                    "telegram_service",
                    f"History download failed (attempt {attempt}/{attempts}): {exc}",
                )
                if attempt >= attempts:
                    self.log_service.log_error(
                        module="telegram_service",
                        error_type=exc.__class__.__name__,
                        error_message=f"History download aborted after {attempts} attempts: {exc}",
                    )
                    return
                await asyncio.sleep(min(5 * attempt, 20))

    async def run_forever(self) -> None:
        self.log_service.log_system("info", "telegram_service", "Listening for new Telegram messages")
        await asyncio.Event().wait()

    async def fetch_message(self, chat_id: int, message_id: int) -> Message | None:
        attempts = 3
        for attempt in range(1, attempts + 1):
            try:
                message = await self.client.get_messages(chat_id=chat_id, message_ids=message_id)
                if not message:
                    return None
                if not (message.video or message.photo or message.document):
                    return None
                return message
            except Exception as exc:
                self.log_service.log_system(
                    "warning",
                    "telegram_service",
                    f"Failed to fetch message {chat_id}:{message_id} (attempt {attempt}/{attempts}): {exc}",
                )
                if attempt < attempts:
                    await asyncio.sleep(attempt)
        return None

import asyncio

from backend_db import initialize_database
from download_service import DownloadService
from log_service import LogService
from runtime_config import load_runtime_config
from sync_service import SyncService
from telegram_service import TelegramService


async def main() -> None:
    config = load_runtime_config()

    initialize_database()

    log_service = LogService()
    sync_service = SyncService(log_service)
    download_service = DownloadService(config, log_service, sync_service)

    telegram_service = TelegramService(
        config=config,
        log_service=log_service,
        sync_service=sync_service,
        on_media_message=download_service.enqueue_message,
        has_message_record=download_service.has_download_record,
    )

    await telegram_service.start()
    download_service.set_message_fetcher(telegram_service.fetch_message)
    download_service.start_worker()

    await telegram_service.download_history()
    await telegram_service.run_forever()


if __name__ == "__main__":
    asyncio.run(main())


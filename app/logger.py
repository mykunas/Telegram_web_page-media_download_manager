import json
import logging
import os
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from backend_db import ErrorLog, SystemLog, db_session_scope


class AppLogger:
    """Unified logger that writes to console, file and database."""

    def __init__(self, name: str = "telegram_downloader") -> None:
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        if not self._logger.handlers:
            formatter = logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

            log_file = os.getenv("LOG_FILE", "/app/logs/downloader.log")
            log_path = Path(log_file)
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
            except Exception:
                # Fallback to current directory when /app path is unavailable.
                fallback = Path("downloader.log")
                file_handler = RotatingFileHandler(fallback, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")

            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

    def _db_write_system(self, level: str, module: str, message: str, extra_json: dict[str, Any] | None) -> None:
        try:
            with db_session_scope() as db:
                db.add(
                    SystemLog(
                        level=level.upper(),
                        module=module,
                        message=message,
                        extra_json=extra_json,
                        created_at=datetime.now(timezone.utc),
                    )
                )
        except Exception as exc:
            self._logger.error("DB write system log failed: %s", exc)

    def _db_write_error(
        self,
        module: str,
        error_type: str,
        error_message: str,
        traceback_text: str | None,
        chat_id: int | None,
        message_id: int | None,
        file_path: str | None,
    ) -> None:
        try:
            with db_session_scope() as db:
                db.add(
                    ErrorLog(
                        module=module,
                        chat_id=chat_id,
                        message_id=message_id,
                        file_path=file_path,
                        error_type=error_type,
                        error_message=error_message,
                        traceback=traceback_text,
                        resolved=False,
                        created_at=datetime.now(timezone.utc),
                    )
                )
        except Exception as exc:
            self._logger.error("DB write error log failed: %s", exc)

    def _emit(self, level: int, module: str, message: str, extra_json: dict[str, Any] | None = None) -> None:
        payload = {
            "level": logging.getLevelName(level),
            "module": module,
            "message": message,
            "extra_json": extra_json,
        }

        self._logger.log(level, json.dumps(payload, ensure_ascii=False))
        self._db_write_system(payload["level"], module, message, extra_json)

    def log_info(self, module: str, message: str, extra_json: dict[str, Any] | None = None) -> None:
        self._emit(logging.INFO, module, message, extra_json)

    def log_warning(self, module: str, message: str, extra_json: dict[str, Any] | None = None) -> None:
        self._emit(logging.WARNING, module, message, extra_json)

    def log_error(
        self,
        module: str,
        message: str,
        extra_json: dict[str, Any] | None = None,
        exc: Exception | None = None,
        chat_id: int | None = None,
        message_id: int | None = None,
        file_path: str | None = None,
        error_type: str | None = None,
        traceback_text: str | None = None,
    ) -> None:
        resolved_error_type = error_type or (exc.__class__.__name__ if exc else "Error")
        resolved_traceback = traceback_text or (traceback.format_exc() if exc else None)

        merged_extra = dict(extra_json or {})
        merged_extra.update(
            {
                "error_type": resolved_error_type,
                "chat_id": chat_id,
                "message_id": message_id,
                "file_path": file_path,
            }
        )

        self._emit(logging.ERROR, module, message, merged_extra)
        self._db_write_error(
            module=module,
            error_type=resolved_error_type,
            error_message=message,
            traceback_text=resolved_traceback,
            chat_id=chat_id,
            message_id=message_id,
            file_path=file_path,
        )


def get_logger() -> AppLogger:
    return AppLogger()

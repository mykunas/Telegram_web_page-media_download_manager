from logger import AppLogger, get_logger


class LogService:
    """Backward-compatible logging facade used by existing services."""

    def __init__(self, logger: AppLogger | None = None) -> None:
        self.logger = logger or get_logger()

    def log_info(self, module: str, message: str, extra_json: dict | None = None) -> None:
        self.logger.log_info(module=module, message=message, extra_json=extra_json)

    def log_warning(self, module: str, message: str, extra_json: dict | None = None) -> None:
        self.logger.log_warning(module=module, message=message, extra_json=extra_json)

    def log_error(
        self,
        module: str,
        error_type: str,
        error_message: str,
        traceback_text: str | None = None,
        chat_id: int | None = None,
        message_id: int | None = None,
        file_path: str | None = None,
        extra_json: dict | None = None,
    ) -> None:
        self.logger.log_error(
            module=module,
            message=error_message,
            extra_json=extra_json,
            chat_id=chat_id,
            message_id=message_id,
            file_path=file_path,
            error_type=error_type,
            traceback_text=traceback_text,
        )

    def log_system(self, level: str, module: str, message: str, extra_json: dict | None = None) -> None:
        normalized = level.lower()
        if normalized == "info":
            self.log_info(module=module, message=message, extra_json=extra_json)
        elif normalized == "warning":
            self.log_warning(module=module, message=message, extra_json=extra_json)
        elif normalized == "error":
            self.log_error(
                module=module,
                error_type="SystemError",
                error_message=message,
                extra_json=extra_json,
            )
        else:
            self.log_info(module=module, message=message, extra_json=extra_json)

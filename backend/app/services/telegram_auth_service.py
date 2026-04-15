from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from pyrogram import Client
from pyrogram.errors import PhoneCodeExpired, PhoneCodeInvalid, SessionPasswordNeeded, Unauthorized

from app.core.exceptions import AppException
from app.services.telegram_config_service import TelegramAuthConfig


@dataclass
class AuthRuntimeState:
    step: str = "idle"
    authorized: bool = False
    phone_code_hash: str | None = None
    message: str = "未开始授权"
    phone_number: str | None = None
    session_name: str | None = None
    user_id: int | None = None
    user_name: str | None = None


class TelegramAuthService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._state = AuthRuntimeState()
        self._client: Client | None = None
        self._config: TelegramAuthConfig | None = None

    def _normalize_session_name(self, session_name: str) -> str:
        name = (session_name or "").strip()
        if not name:
            return "/app/session/telegram_user"
        if name.endswith(".session"):
            name = name[: -len(".session")]
        return name

    def _build_client(self, config: TelegramAuthConfig) -> Client:
        session_name = self._normalize_session_name(config.session_name)
        session_path = Path(session_name)
        if session_path.parent and str(session_path.parent) not in {"", "."}:
            session_path.parent.mkdir(parents=True, exist_ok=True)

        return Client(
            name=session_name,
            api_id=config.api_id,
            api_hash=config.api_hash,
            phone_number=config.phone_number,
        )

    def _ensure_event_loop(self) -> None:
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

    def _close_client(self) -> None:
        if not self._client:
            return
        try:
            self._client.disconnect()
        except Exception:
            pass
        finally:
            self._client = None

    def _session_paths(self, session_name: str) -> list[Path]:
        base_name = self._normalize_session_name(session_name)
        session_path = Path(base_name)
        if session_path.suffix != ".session":
            session_path = Path(f"{session_path}.session")
        return [
            session_path,
            Path(f"{session_path}-journal"),
            Path(f"{session_path}-wal"),
            Path(f"{session_path}-shm"),
        ]

    def _session_candidates(self, session_name: str) -> list[Path]:
        candidates: list[Path] = []
        for path in self._session_paths(session_name):
            candidates.append(path)
            if not path.is_absolute():
                candidates.append(Path.cwd() / path)

        unique: list[Path] = []
        seen: set[str] = set()
        for path in candidates:
            key = str(path)
            if key in seen:
                continue
            seen.add(key)
            unique.append(path)
        return unique

    def _session_file_exists(self, session_name: str) -> bool:
        return any(path.exists() and path.is_file() for path in self._session_candidates(session_name))

    def _is_session_locked_error(self, exc: Exception) -> bool:
        text = str(exc).lower()
        markers = (
            "database is locked",
            "database table is locked",
            "resource temporarily unavailable",
            "sqlite",
            "locked",
            "busy",
        )
        return any(marker in text for marker in markers)

    def _remove_local_session_files(self, session_name: str) -> None:
        for path in self._session_candidates(session_name):
            if path.exists() and path.is_file():
                path.unlink()

    def start_authorization(self, config: TelegramAuthConfig) -> dict:
        with self._lock:
            self._close_client()
            self._config = config

            try:
                self._ensure_event_loop()
                self._client = self._build_client(config)
                self._client.connect()
                sent_code = self._client.send_code(config.phone_number)
            except Exception as exc:
                self._state = AuthRuntimeState(step="error", message=f"发送验证码失败: {exc}")
                self._close_client()
                raise AppException(self._state.message, status_code=400) from exc

            self._state = AuthRuntimeState(
                step="code_required",
                authorized=False,
                phone_code_hash=sent_code.phone_code_hash,
                message="验证码已发送，请提交验证码",
                phone_number=config.phone_number,
                session_name=self._normalize_session_name(config.session_name),
            )
            return self._status_payload()

    def submit_code(self, code: str) -> dict:
        with self._lock:
            if not self._client or not self._config or not self._state.phone_code_hash:
                raise AppException("请先执行“保存并开始授权”", status_code=400)

            try:
                self._ensure_event_loop()
                user = self._client.sign_in(
                    phone_number=self._config.phone_number,
                    phone_code_hash=self._state.phone_code_hash,
                    phone_code=code.strip(),
                )
                self._state.step = "authorized"
                self._state.authorized = True
                self._state.message = "授权成功"
                self._state.user_id = int(user.id)
                self._state.user_name = user.first_name or user.username
                self._state.phone_code_hash = None
            except SessionPasswordNeeded:
                self._state.step = "password_required"
                self._state.authorized = False
                self._state.message = "该账号已开启二步验证，请提交二步验证密码"
            except PhoneCodeInvalid as exc:
                self._state.step = "code_required"
                self._state.message = "验证码错误，请重新输入"
                raise AppException(self._state.message, status_code=400) from exc
            except PhoneCodeExpired as exc:
                self._state.step = "code_required"
                self._state.message = "验证码已过期，请重新点击开始授权"
                raise AppException(self._state.message, status_code=400) from exc
            except Exception as exc:
                self._state.step = "error"
                self._state.message = f"提交验证码失败: {exc}"
                raise AppException(self._state.message, status_code=400) from exc

            return self._status_payload()

    def submit_password(self, password: str) -> dict:
        with self._lock:
            if not self._client or not self._config:
                raise AppException("请先执行“保存并开始授权”", status_code=400)

            try:
                self._ensure_event_loop()
                user = self._client.check_password(password.strip())
                self._state.step = "authorized"
                self._state.authorized = True
                self._state.message = "二步验证通过，授权成功"
                self._state.user_id = int(user.id)
                self._state.user_name = user.first_name or user.username
            except Exception as exc:
                self._state.step = "password_required"
                self._state.authorized = False
                self._state.message = f"二步验证失败: {exc}"
                raise AppException(self._state.message, status_code=400) from exc

            return self._status_payload()

    def status(self, config: TelegramAuthConfig | None) -> dict:
        with self._lock:
            if self._state.authorized:
                return self._status_payload()

            if config:
                try:
                    self._ensure_event_loop()
                    probe_client = self._build_client(config)
                    probe_client.connect()
                    user = probe_client.get_me()
                    probe_client.disconnect()

                    self._state.step = "authorized"
                    self._state.authorized = True
                    self._state.message = "检测到本地会话已授权"
                    self._state.phone_number = config.phone_number
                    self._state.session_name = self._normalize_session_name(config.session_name)
                    self._state.user_id = int(user.id)
                    self._state.user_name = user.first_name or user.username
                except Unauthorized:
                    self._state.step = self._state.step if self._state.step in {"code_required", "password_required"} else "idle"
                    self._state.authorized = False
                    if self._state.step == "idle":
                        self._state.message = "当前未授权"
                except Exception as exc:
                    # Session sqlite may be locked by running worker process.
                    # If local session file exists, treat as authorized/in-use to avoid false re-auth prompts.
                    if self._is_session_locked_error(exc) and self._session_file_exists(config.session_name):
                        self._state.step = "authorized"
                        self._state.authorized = True
                        self._state.message = "检测到会话文件被占用，按已授权处理"
                        self._state.phone_number = config.phone_number
                        self._state.session_name = self._normalize_session_name(config.session_name)
                    # Other probe errors keep runtime state unchanged.

            return self._status_payload()

    def disconnect(self, config: TelegramAuthConfig | None) -> dict:
        with self._lock:
            self._close_client()

            session_name = config.session_name if config else self._state.session_name
            if session_name:
                self._remove_local_session_files(session_name)

            self._config = None
            self._state = AuthRuntimeState(message="会话已断开")
            return self._status_payload()

    def _status_payload(self) -> dict:
        return {
            "step": self._state.step,
            "authorized": self._state.authorized,
            "message": self._state.message,
            "phone_number": self._state.phone_number,
            "session_name": self._state.session_name,
            "user_id": self._state.user_id,
            "user_name": self._state.user_name,
        }


telegram_auth_service = TelegramAuthService()

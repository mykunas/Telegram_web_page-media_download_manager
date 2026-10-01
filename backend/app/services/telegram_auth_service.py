from __future__ import annotations

import asyncio
import os
import time
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
    message: str = "Authorization not started"
    phone_number: str | None = None
    session_name: str | None = None
    user_id: int | None = None
    user_name: str | None = None
    expires_at: float | None = None


class TelegramAuthService:
    def __init__(self) -> None:
        self._lock = Lock()
        self._state = AuthRuntimeState()
        self._client: Client | None = None
        self._config: TelegramAuthConfig | None = None

    def _normalize_session_name(self, session_name: str) -> str:
        name = (session_name or "").strip()
        if name.endswith(".session"):
            name = name[: -len(".session")]
        return name or "/app/session/telegram_user"

    def _build_client(self, config: TelegramAuthConfig) -> Client:
        session_name = self._normalize_session_name(config.session_name)
        session_path = Path(session_name)
        session_path.parent.mkdir(parents=True, exist_ok=True)
        self._secure_permissions(session_path.parent, 0o700)
        return Client(
            name=session_name,
            api_id=config.api_id,
            api_hash=config.api_hash,
            phone_number=config.phone_number,
        )

    @staticmethod
    def _secure_permissions(path: Path, mode: int) -> None:
        try:
            os.chmod(path, mode)
        except OSError:
            # Docker Desktop bind mounts may not support chmod. Deployment docs
            # describe the host-side permissions for Linux/NAS.
            pass

    def _secure_session_files(self, session_name: str) -> None:
        for path in self._session_paths(session_name):
            if path.is_file():
                self._secure_permissions(path, 0o600)

    @staticmethod
    def _ensure_event_loop() -> None:
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

    def _close_client(self) -> None:
        if not self._client:
            return
        try:
            self._client.disconnect()
        except Exception:
            pass
        finally:
            self._client = None

    def _clear_transient_auth(self, *, close_client: bool) -> None:
        self._state.phone_code_hash = None
        self._config = None
        if close_client:
            self._close_client()

    def _session_paths(self, session_name: str) -> list[Path]:
        base = Path(self._normalize_session_name(session_name))
        session_path = base if base.suffix == ".session" else Path(f"{base}.session")
        return [
            session_path,
            Path(f"{session_path}-journal"),
            Path(f"{session_path}-wal"),
            Path(f"{session_path}-shm"),
        ]

    def _session_file_exists(self, session_name: str) -> bool:
        return any(path.is_file() for path in self._session_paths(session_name))

    @staticmethod
    def _is_session_locked_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(marker in text for marker in ("database is locked", "database table is locked", "locked", "busy"))

    def _remove_local_session_files(self, session_name: str) -> None:
        for path in self._session_paths(session_name):
            if path.is_file():
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
                self._state = AuthRuntimeState(step="error", message="Failed to send verification code")
                self._clear_transient_auth(close_client=True)
                raise AppException("Failed to send verification code", status_code=400) from exc

            self._state = AuthRuntimeState(
                step="code_required",
                authorized=False,
                phone_code_hash=sent_code.phone_code_hash,
                message="Verification code sent",
                phone_number=config.phone_number,
                session_name=self._normalize_session_name(config.session_name),
                expires_at=time.monotonic() + 600,
            )
            return self._status_payload()

    def submit_code(self, code: str) -> dict:
        with self._lock:
            if self._state.expires_at and time.monotonic() >= self._state.expires_at:
                self._state = AuthRuntimeState(message="Authorization state expired; start again")
                self._clear_transient_auth(close_client=True)
                raise AppException("Authorization state expired; start again", status_code=400)
            if not self._client or not self._config or not self._state.phone_code_hash:
                raise AppException("Start authorization before submitting a code", status_code=400)
            try:
                self._ensure_event_loop()
                user = self._client.sign_in(
                    phone_number=self._config.phone_number,
                    phone_code_hash=self._state.phone_code_hash,
                    phone_code=code.strip(),
                )
                self._mark_authorized(user)
                self._secure_session_files(self._state.session_name or self._config.session_name)
                self._clear_transient_auth(close_client=True)
            except SessionPasswordNeeded:
                self._state.step = "password_required"
                self._state.authorized = False
                self._state.message = "Two-factor password required"
            except PhoneCodeInvalid as exc:
                self._state.step = "code_required"
                self._state.message = "Verification code is invalid"
                raise AppException(self._state.message, status_code=400) from exc
            except PhoneCodeExpired as exc:
                self._state = AuthRuntimeState(step="idle", message="Verification code expired; start again")
                self._clear_transient_auth(close_client=True)
                raise AppException("Verification code expired; start again", status_code=400) from exc
            except Exception as exc:
                self._state = AuthRuntimeState(step="error", message="Verification code submission failed")
                self._clear_transient_auth(close_client=True)
                raise AppException("Verification code submission failed", status_code=400) from exc
            return self._status_payload()

    def submit_password(self, password: str) -> dict:
        with self._lock:
            if self._state.expires_at and time.monotonic() >= self._state.expires_at:
                self._state = AuthRuntimeState(message="Authorization state expired; start again")
                self._clear_transient_auth(close_client=True)
                raise AppException("Authorization state expired; start again", status_code=400)
            if not self._client or not self._config:
                raise AppException("Start authorization before submitting a password", status_code=400)
            try:
                self._ensure_event_loop()
                user = self._client.check_password(password.strip())
                self._mark_authorized(user)
                self._secure_session_files(self._state.session_name or self._config.session_name)
                self._clear_transient_auth(close_client=True)
            except Exception as exc:
                self._state.step = "password_required"
                self._state.authorized = False
                self._state.message = "Two-factor verification failed"
                raise AppException(self._state.message, status_code=400) from exc
            return self._status_payload()

    def _mark_authorized(self, user) -> None:
        self._state.step = "authorized"
        self._state.authorized = True
        self._state.message = "Authorization successful"
        self._state.user_id = int(user.id)
        self._state.user_name = user.first_name or user.username
        self._state.phone_code_hash = None

    def status(self, config: TelegramAuthConfig | None) -> dict:
        with self._lock:
            if self._state.expires_at and time.monotonic() >= self._state.expires_at:
                self._state = AuthRuntimeState(message="Authorization state expired; start again")
                self._clear_transient_auth(close_client=True)
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
                    self._state.message = "Existing Telegram session is authorized"
                    self._state.phone_number = config.phone_number
                    self._state.session_name = self._normalize_session_name(config.session_name)
                    self._state.user_id = int(user.id)
                    self._state.user_name = user.first_name or user.username
                except Unauthorized:
                    if self._state.step not in {"code_required", "password_required"}:
                        self._state = AuthRuntimeState(message="Telegram session is not authorized")
                except Exception as exc:
                    if self._is_session_locked_error(exc) and self._session_file_exists(config.session_name):
                        self._state.step = "authorized"
                        self._state.authorized = True
                        self._state.message = "Telegram session exists and is in use"
                        self._state.phone_number = config.phone_number
                        self._state.session_name = self._normalize_session_name(config.session_name)
            return self._status_payload()

    def disconnect(self, config: TelegramAuthConfig | None) -> dict:
        with self._lock:
            session_name = config.session_name if config else self._state.session_name
            self._close_client()
            self._config = None
            self._state = AuthRuntimeState(
                message="Client disconnected; session retained",
                session_name=self._normalize_session_name(session_name) if session_name else None,
            )
            return self._status_payload()

    def delete_session(self, config: TelegramAuthConfig, *, confirmation: str) -> dict:
        if confirmation != "DELETE_SESSION":
            raise AppException("confirmation must equal DELETE_SESSION", status_code=400)
        with self._lock:
            self._close_client()
            try:
                self._remove_local_session_files(config.session_name)
            except OSError as exc:
                raise AppException("Telegram session could not be deleted; stop the worker and retry", status_code=409) from exc
            self._config = None
            self._state = AuthRuntimeState(message="Telegram session deleted")
            return self._status_payload()

    def _status_payload(self) -> dict:
        return {
            "step": self._state.step,
            "authorized": self._state.authorized,
            "message": self._state.message,
            "phone_number": self._state.phone_number,
            "session_exists": bool(self._state.session_name and self._session_file_exists(self._state.session_name)),
            "user_id": self._state.user_id,
            "user_name": self._state.user_name,
        }


telegram_auth_service = TelegramAuthService()

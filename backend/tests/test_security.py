from __future__ import annotations

import hashlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("ADMIN_AUTH_ENABLED", "false")

from app.api.settings import batch_update_settings, list_settings  # noqa: E402
from app.api.telegram_config import get_telegram_config  # noqa: E402
from app.core.admin_auth import AdminWriteProtectionMiddleware, verify_admin_token  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.config_registry import validate_config_value  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.core.exceptions import AppException  # noqa: E402
from app.core.security import REDACTED, sanitize_for_log, sanitize_text  # noqa: E402
from app.models import AppSetting  # noqa: E402
from app.schemas.setting import SettingBatchUpdateRequest, SettingUpdateItem  # noqa: E402
from app.services.telegram_config_service import (  # noqa: E402
    read_telegram_public_view,
    save_secret_values,
)
from fastapi import Request, Response  # noqa: E402


VALID_HASH = "a" * 32
VALID_PHONE = "+8613800000000"


class SecurityRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add_all(
            [
                AppSetting(key="API_ID", value="123456", value_type="integer", description="test"),
                AppSetting(key="API_HASH", value=VALID_HASH, value_type="string", description="test"),
                AppSetting(key="PHONE_NUMBER", value=VALID_PHONE, value_type="string", description="test"),
                AppSetting(
                    key="SESSION_NAME",
                    value="/app/session/telegram_user",
                    value_type="string",
                    description="test",
                ),
                AppSetting(key="HISTORY_LIMIT", value="2000", value_type="integer", description="test"),
            ]
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_telegram_config_never_returns_raw_secrets(self) -> None:
        response = Response()
        with patch("app.api.telegram_config.telegram_auth_service.status", return_value={"step": "idle"}):
            payload = get_telegram_config(response=response, db=self.db)
        serialized = str(payload)
        self.assertNotIn(VALID_HASH, serialized)
        self.assertNotIn(VALID_PHONE, serialized)
        self.assertTrue(payload["data"]["telegram"]["API_HASH"]["configured"])
        self.assertEqual(response.headers["cache-control"], "no-store, max-age=0")

    def test_settings_api_filters_secret_rows(self) -> None:
        payload = list_settings(db=self.db)
        keys = {item["key"] for item in payload["data"]}
        self.assertNotIn("API_HASH", keys)
        self.assertNotIn("PHONE_NUMBER", keys)
        self.assertIn("HISTORY_LIMIT", keys)

    def test_secret_update_remains_masked(self) -> None:
        replacement = "b" * 32
        save_secret_values(self.db, {"API_HASH": replacement})
        public = read_telegram_public_view(self.db)
        self.assertTrue(public["API_HASH"]["configured"])
        self.assertNotIn(replacement, str(public))

    def test_empty_secret_does_not_overwrite_existing_value(self) -> None:
        save_secret_values(self.db, {"API_HASH": "", "PHONE_NUMBER": None})
        rows = dict(self.db.query(AppSetting.key, AppSetting.value).all())
        self.assertEqual(rows["API_HASH"], VALID_HASH)
        self.assertEqual(rows["PHONE_NUMBER"], VALID_PHONE)

    def test_auth_transients_are_not_database_settings(self) -> None:
        keys = {row.key.lower() for row in self.db.query(AppSetting).all()}
        self.assertNotIn("code", keys)
        self.assertNotIn("password", keys)
        self.assertNotIn("phone_code_hash", keys)

    def test_log_sanitizes_api_hash_password_and_phone(self) -> None:
        text = sanitize_text(
            f"api_hash={VALID_HASH} password=hunter2 phone_number={VALID_PHONE} token=abc"
        )
        self.assertNotIn(VALID_HASH, text)
        self.assertNotIn("hunter2", text)
        self.assertNotIn(VALID_PHONE, text)
        self.assertIn(REDACTED, text)
        structured = sanitize_for_log({"password": "secret", "nested": {"api_hash": VALID_HASH}})
        self.assertEqual(structured["password"], REDACTED)
        self.assertEqual(structured["nested"]["api_hash"], REDACTED)

    def test_invalid_config_is_rejected(self) -> None:
        with self.assertRaises(AppException):
            validate_config_value("API_HASH", "not-a-hash")
        with self.assertRaises(AppException):
            validate_config_value("MAX_RETRIES", 999)

    def test_batch_validation_rolls_back_all_values(self) -> None:
        payload = SettingBatchUpdateRequest(
            items=[
                SettingUpdateItem(key="HISTORY_LIMIT", value=5000),
                SettingUpdateItem(key="MAX_RETRIES", value=999),
            ]
        )
        with self.assertRaises(AppException):
            batch_update_settings(payload=payload, db=self.db)
        row = self.db.query(AppSetting).filter(AppSetting.key == "HISTORY_LIMIT").one()
        self.assertEqual(row.value, "2000")

    def test_path_traversal_is_rejected(self) -> None:
        for value in ("/", "../../etc", "/app/downloads/../../etc", "/tmp/media"):
            with self.subTest(value=value), self.assertRaises(AppException):
                validate_config_value("DOWNLOAD_DIR", value)
        with self.assertRaises(AppException):
            validate_config_value("SESSION_NAME", "/etc/telegram")

    def test_optional_admin_token(self) -> None:
        token = "correct horse battery staple"
        digest = hashlib.sha256(token.encode()).hexdigest()
        with (
            patch.object(settings, "ADMIN_AUTH_ENABLED", True),
            patch.object(settings, "ADMIN_API_TOKEN_HASH", SecretStr(digest)),
        ):
            self.assertFalse(verify_admin_token(None))
            self.assertFalse(verify_admin_token("Bearer wrong"))
            self.assertTrue(verify_admin_token(f"Bearer {token}"))


class AdminMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _request(method: str, path: str, token: str | None = None) -> Request:
        headers = [] if token is None else [(b"authorization", f"Bearer {token}".encode())]
        return Request(
            {
                "type": "http",
                "method": method,
                "path": path,
                "headers": headers,
                "query_string": b"",
                "scheme": "http",
                "server": ("test", 80),
                "client": ("127.0.0.1", 1234),
            }
        )

    async def test_admin_middleware_blocks_unauthenticated_write(self) -> None:
        token = "admin-test-token"
        digest = hashlib.sha256(token.encode()).hexdigest()
        middleware = AdminWriteProtectionMiddleware(app=lambda *_: None)

        async def allowed(_: Request) -> Response:
            return Response(status_code=204)

        with (
            patch.object(settings, "ADMIN_AUTH_ENABLED", True),
            patch.object(settings, "ADMIN_API_TOKEN_HASH", SecretStr(digest)),
        ):
            blocked = await middleware.dispatch(self._request("PUT", "/api/settings"), allowed)
            accepted = await middleware.dispatch(self._request("PUT", "/api/settings", token), allowed)
        self.assertEqual(blocked.status_code, 401)
        self.assertEqual(accepted.status_code, 204)

    async def test_media_get_is_not_blocked(self) -> None:
        middleware = AdminWriteProtectionMiddleware(app=lambda *_: None)

        async def allowed(_: Request) -> Response:
            return Response(status_code=200)

        with patch.object(settings, "ADMIN_AUTH_ENABLED", True):
            response = await middleware.dispatch(self._request("GET", "/api/downloads/1/file"), allowed)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()

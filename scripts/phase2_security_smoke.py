"""Run inside the backend container against a live Phase 2 instance."""

from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000/api"
DATABASE = "/app/data/app.db"


def request(path: str, *, method: str = "GET", payload: dict | None = None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status, response.headers, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers, exc.read().decode()


with sqlite3.connect(DATABASE) as conn:
    stored = dict(conn.execute("SELECT key,value FROM app_settings").fetchall())

status, headers, telegram_body = request("/telegram-config")
assert status == 200
assert headers.get("Cache-Control") == "no-store, max-age=0"
for key in ("API_HASH", "PHONE_NUMBER"):
    assert not stored.get(key) or stored[key] not in telegram_body

status, _, settings_body = request("/settings")
assert status == 200
assert "API_HASH" not in settings_body
assert "PHONE_NUMBER" not in settings_body

before_hash = stored.get("API_HASH")
status, _, _ = request(
    "/telegram-config/telegram",
    method="PUT",
    payload={"API_ID": "", "API_HASH": "", "PHONE_NUMBER": "", "SESSION_NAME": ""},
)
assert status == 200
with sqlite3.connect(DATABASE) as conn:
    after_hash = conn.execute("SELECT value FROM app_settings WHERE key='API_HASH'").fetchone()[0]
assert before_hash == after_hash

before_limit = stored.get("HISTORY_LIMIT")
status, _, _ = request(
    "/settings",
    method="PUT",
    payload={
        "items": [
            {"key": "HISTORY_LIMIT", "value": 5000},
            {"key": "MAX_RETRIES", "value": 999},
        ]
    },
)
assert status == 422
with sqlite3.connect(DATABASE) as conn:
    after_limit = conn.execute("SELECT value FROM app_settings WHERE key='HISTORY_LIMIT'").fetchone()[0]
assert before_limit == after_limit

status, _, _ = request(
    "/telegram-config/download",
    method="PUT",
    payload={
        "DOWNLOAD_DIR": "/app/downloads/../../etc",
        "TARGET_CHATS": "",
        "ALLOW_EXTS": ".mp4",
        "DOWNLOAD_HISTORY": True,
        "HISTORY_LIMIT": 2000,
        "MAX_RETRIES": 3,
        "RETRY_DELAY": 5,
        "MAX_FILE_SIZE_MB": 0,
    },
)
assert status == 422

with sqlite3.connect(DATABASE) as conn:
    transient_count = conn.execute(
        "SELECT COUNT(*) FROM app_settings WHERE lower(key) IN ('code','password','phone_code_hash')"
    ).fetchone()[0]
assert transient_count == 0

print("phase2_live_security_smoke=passed")

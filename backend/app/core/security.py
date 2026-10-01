from __future__ import annotations

import re
from pathlib import PurePath
from typing import Any


REDACTED = "[REDACTED]"
SENSITIVE_KEYS = {
    "api_hash",
    "phone_number",
    "password",
    "two_factor_password",
    "2fa",
    "code",
    "phone_code",
    "phone_code_hash",
    "token",
    "authorization",
    "cookie",
    "session",
    "session_name",
}


def mask_secret(value: Any, *, head: int = 4, tail: int = 3) -> str:
    text = "" if value is None else str(value)
    if not text:
        return ""
    if len(text) <= head + tail:
        return "•" * len(text)
    return f"{text[:head]}{'•' * 8}{text[-tail:]}"


def mask_phone(value: Any) -> str:
    text = "" if value is None else str(value)
    digits = re.sub(r"\D", "", text)
    if not digits:
        return ""
    country_prefix = "+" + digits[: max(1, len(digits) - 10)]
    tail = digits[-4:] if len(digits) >= 4 else digits[-1:]
    return f"{country_prefix}******{tail}"


def mask_session_name(value: Any) -> str:
    text = "" if value is None else str(value)
    if not text:
        return ""
    name = PurePath(text).name
    if name.endswith(".session"):
        name = name[: -len(".session")]
    return mask_secret(name, head=2, tail=2)


def secret_metadata(value: Any, *, kind: str = "secret") -> dict[str, Any]:
    text = "" if value is None else str(value)
    if kind == "phone":
        masked = mask_phone(text)
    elif kind == "session":
        masked = mask_session_name(text)
    elif kind == "api_id":
        masked = mask_secret(text, head=0, tail=4)
    else:
        masked = mask_secret(text)
    return {"configured": bool(text.strip()), "masked": masked}


_KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b(api_hash|phone_number|password|two[_-]?factor[_-]?password|2fa|phone_code_hash|phone_code|code|token|authorization|cookie|session(?:_name)?)\b"
    r"(\s*[:=]\s*)([^\s,;}&]+)"
)
_PHONE_PATTERN = re.compile(r"(?<!\d)\+[1-9]\d{6,14}(?!\d)")
_API_HASH_PATTERN = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])")


def sanitize_text(value: Any) -> str:
    text = "" if value is None else str(value)

    def replace_key_value(match: re.Match[str]) -> str:
        key = match.group(1)
        separator = match.group(2)
        raw_value = match.group(3)
        if key.lower() in {"phone_number"}:
            replacement = mask_phone(raw_value)
        else:
            replacement = REDACTED
        return f"{key}{separator}{replacement}"

    text = _KEY_VALUE_PATTERN.sub(replace_key_value, text)
    text = _API_HASH_PATTERN.sub(REDACTED, text)
    text = _PHONE_PATTERN.sub(lambda match: mask_phone(match.group(0)), text)
    return text


def sanitize_for_log(value: Any, *, key_hint: str | None = None) -> Any:
    if key_hint and key_hint.lower() in SENSITIVE_KEYS:
        if key_hint.lower() == "phone_number":
            return mask_phone(value)
        return REDACTED
    if isinstance(value, dict):
        return {str(key): sanitize_for_log(item, key_hint=str(key)) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_log(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if value is not None:
        return sanitize_text(value)
    return value

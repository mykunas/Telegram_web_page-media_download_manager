from __future__ import annotations

import json
from typing import Any

from app.core.exceptions import AppException

VALID_VALUE_TYPES = {"string", "integer", "float", "boolean", "json"}


def parse_value_by_type(value: str | None, value_type: str) -> Any:
    if value is None:
        return None

    try:
        if value_type == "string":
            return value
        if value_type == "integer":
            return int(value)
        if value_type == "float":
            return float(value)
        if value_type == "boolean":
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            raise ValueError("boolean must be one of true/false/1/0/yes/no/on/off")
        if value_type == "json":
            return json.loads(value)
    except Exception as exc:
        raise AppException(f"invalid value for type '{value_type}': {exc}", status_code=400) from exc

    raise AppException(f"unsupported value_type: {value_type}", status_code=400)


def normalize_value_for_storage(raw_value: Any, value_type: str) -> str | None:
    if raw_value is None:
        return None

    if value_type == "string":
        return str(raw_value)

    if value_type == "integer":
        return str(int(raw_value))

    if value_type == "float":
        return str(float(raw_value))

    if value_type == "boolean":
        if isinstance(raw_value, bool):
            return "true" if raw_value else "false"
        normalized = str(raw_value).strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return "true"
        if normalized in {"0", "false", "no", "off"}:
            return "false"
        raise AppException("invalid boolean value", status_code=400)

    if value_type == "json":
        if isinstance(raw_value, str):
            parsed = json.loads(raw_value)
        else:
            parsed = raw_value
        return json.dumps(parsed, ensure_ascii=False)

    raise AppException(f"unsupported value_type: {value_type}", status_code=400)


def ensure_value_type(value_type: str | None, fallback: str = "string") -> str:
    resolved = (value_type or fallback).strip().lower()
    if resolved not in VALID_VALUE_TYPES:
        raise AppException(
            f"unsupported value_type: {resolved}. allowed: {', '.join(sorted(VALID_VALUE_TYPES))}",
            status_code=400,
        )
    return resolved

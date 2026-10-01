from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.config_registry import (
    CONFIG_REGISTRY,
    decode_storage_value,
    public_runtime_definitions,
    validate_update_batch,
)
from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.response import success_response
from app.core.rate_limit import CONFIG_WRITE_LIMIT
from app.models import AppSetting
from app.schemas.setting import (
    SettingBatchUpdateRequest,
    SettingItemOut,
    SettingReloadResult,
    SettingUpdateResult,
)
from app.services.telegram_config_service import (
    config_change_effect,
    ensure_required_settings,
    save_runtime_values,
)

router = APIRouter(prefix="/settings", tags=["Settings"])
audit_logger = logging.getLogger("security_audit")


def _public_keys() -> tuple[str, ...]:
    return tuple(item.key for item in public_runtime_definitions())


def _to_setting_item(row: AppSetting) -> SettingItemOut:
    definition = CONFIG_REGISTRY[row.key]
    return SettingItemOut(
        id=row.id,
        key=row.key,
        value=row.value,
        value_type=definition.value_type,
        description=definition.description,
        parsed_value=decode_storage_value(row.key, row.value),
        updated_at=row.updated_at,
    )


@router.get("")
def list_settings(db: Session = Depends(get_db)) -> dict:
    keys = _public_keys()
    ensure_required_settings(db, keys)
    rows = db.query(AppSetting).filter(AppSetting.key.in_(keys)).order_by(AppSetting.key.asc()).all()
    return success_response(data=[_to_setting_item(row).model_dump(mode="json") for row in rows])


@router.put("", dependencies=[Depends(CONFIG_WRITE_LIMIT)])
def batch_update_settings(payload: SettingBatchUpdateRequest, db: Session = Depends(get_db)) -> dict:
    if not payload.items:
        raise AppException("items cannot be empty", status_code=400)

    raw_values: dict[str, object] = {}
    for item in payload.items:
        if item.key in raw_values:
            raise AppException(f"duplicate setting key: {item.key}", status_code=400)
        raw_values[item.key] = item.value

    # Validate every item before the first write. This also rejects secrets,
    # bootstrap keys and unknown keys.
    validate_update_batch(raw_values, allow_secrets=False)
    save_runtime_values(db, raw_values)

    rows = db.query(AppSetting).filter(AppSetting.key.in_(tuple(raw_values))).all()
    row_map = {row.key: row for row in rows}
    for key in raw_values:
        audit_logger.info("config_change key=%s action=updated result=success secret=false", key)

    result = SettingUpdateResult(
        updated_count=len(raw_values),
        created_count=0,
        items=[_to_setting_item(row_map[key]) for key in raw_values],
    )
    return success_response(
        data={
            **result.model_dump(mode="json"),
            "updated": True,
            **config_change_effect(raw_values.keys()),
        },
        message="settings updated",
    )


@router.post("/reload", dependencies=[Depends(CONFIG_WRITE_LIMIT)])
def reload_settings(request: Request, db: Session = Depends(get_db)) -> dict:
    keys = _public_keys()
    ensure_required_settings(db, keys)
    rows = db.query(AppSetting).filter(AppSetting.key.in_(keys)).order_by(AppSetting.key.asc()).all()
    runtime_settings = {
        row.key: {
            "value": row.value,
            "value_type": CONFIG_REGISTRY[row.key].value_type,
            "parsed_value": decode_storage_value(row.key, row.value),
            "description": CONFIG_REGISTRY[row.key].description,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    }
    request.app.state.runtime_settings = runtime_settings
    result = SettingReloadResult(
        reloaded_count=len(runtime_settings),
        reloaded_keys=list(runtime_settings.keys()),
    )
    return success_response(
        data={
            **result.model_dump(),
            "restart_required": False,
            "worker_reload_required": bool(runtime_settings),
        },
        message="settings reloaded",
    )

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.response import success_response
from app.models import AppSetting
from app.schemas.setting import (
    SettingBatchUpdateRequest,
    SettingItemOut,
    SettingReloadResult,
    SettingUpdateResult,
)
from app.services.settings_service import ensure_value_type, normalize_value_for_storage, parse_value_by_type

router = APIRouter(prefix="/settings", tags=["Settings"])


def _to_setting_item(row: AppSetting) -> SettingItemOut:
    return SettingItemOut(
        id=row.id,
        key=row.key,
        value=row.value,
        value_type=row.value_type,
        description=row.description,
        parsed_value=parse_value_by_type(row.value, row.value_type),
        updated_at=row.updated_at,
    )


@router.get("")
def list_settings(db: Session = Depends(get_db)) -> dict:
    rows = db.query(AppSetting).order_by(AppSetting.key.asc()).all()
    data = [_to_setting_item(row).model_dump(mode="json") for row in rows]
    return success_response(data=data)


@router.put("")
def batch_update_settings(payload: SettingBatchUpdateRequest, db: Session = Depends(get_db)) -> dict:
    if not payload.items:
        raise AppException("items cannot be empty", status_code=400)

    now = datetime.now(UTC)
    created_count = 0
    updated_count = 0
    changed_rows: list[AppSetting] = []

    try:
        for item in payload.items:
            row = db.query(AppSetting).filter(AppSetting.key == item.key).first()

            if row:
                resolved_value_type = ensure_value_type(item.value_type, fallback=row.value_type)
                normalized_value = normalize_value_for_storage(item.value, resolved_value_type)

                row.value_type = resolved_value_type
                row.value = normalized_value
                if item.description is not None:
                    row.description = item.description
                row.updated_at = now

                updated_count += 1
                changed_rows.append(row)
            else:
                resolved_value_type = ensure_value_type(item.value_type, fallback="string")
                normalized_value = normalize_value_for_storage(item.value, resolved_value_type)

                row = AppSetting(
                    key=item.key,
                    value=normalized_value,
                    value_type=resolved_value_type,
                    description=item.description,
                    updated_at=now,
                )
                db.add(row)
                db.flush()

                created_count += 1
                changed_rows.append(row)

        db.commit()

    except AppException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise AppException(f"failed to update settings: {exc}", status_code=500) from exc

    result = SettingUpdateResult(
        updated_count=updated_count,
        created_count=created_count,
        items=[_to_setting_item(row) for row in changed_rows],
    )
    return success_response(data=result.model_dump(mode="json"), message="settings updated")


@router.post("/reload")
def reload_settings(request: Request, db: Session = Depends(get_db)) -> dict:
    rows = db.query(AppSetting).order_by(AppSetting.key.asc()).all()

    runtime_settings = {
        row.key: {
            "value": row.value,
            "value_type": row.value_type,
            "parsed_value": parse_value_by_type(row.value, row.value_type),
            "description": row.description,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    }

    request.app.state.runtime_settings = runtime_settings

    result = SettingReloadResult(
        reloaded_count=len(runtime_settings),
        reloaded_keys=list(runtime_settings.keys()),
    )
    return success_response(data=result.model_dump(), message="settings reloaded")

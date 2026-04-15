from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.response import success_response
from app.models import SyncStatus
from app.schemas.sync import SyncServiceActionResult, SyncStatusListData, SyncStatusOut
from app.services.sync_manager import SyncManager

router = APIRouter(prefix="/sync", tags=["Sync"])


def _manager(request: Request) -> SyncManager:
    return SyncManager(request.app.state)


def _to_sync_status_out(row: SyncStatus) -> SyncStatusOut:
    return SyncStatusOut(
        id=row.id,
        chat_id=row.chat_id,
        last_scanned_message_id=row.last_scanned_message_id,
        last_downloaded_message_id=row.last_downloaded_message_id,
        total_found=row.total_found,
        total_success=row.total_success,
        total_failed=row.total_failed,
        total_skipped=row.total_skipped,
        missing_count=row.missing_count,
        sync_status=row.sync_status,
        last_sync_at=row.last_sync_at,
    )


@router.get("/status")
def list_sync_statuses(request: Request, db: Session = Depends(get_db)) -> dict:
    rows = db.query(SyncStatus).order_by(SyncStatus.chat_id.asc()).all()
    manager = _manager(request)

    payload = SyncStatusListData(
        service=manager.get_runtime_status(),
        count=len(rows),
        channels=[_to_sync_status_out(row) for row in rows],
    )
    return success_response(data=payload.model_dump(mode="json"))


@router.get("/status/{chat_id}")
def get_sync_status(chat_id: int, request: Request, db: Session = Depends(get_db)) -> dict:
    row = db.query(SyncStatus).filter(SyncStatus.chat_id == chat_id).first()
    if not row:
        raise AppException("sync status not found", status_code=404)

    manager = _manager(request)
    return success_response(
        data={
            "service": manager.get_runtime_status(),
            "channel": _to_sync_status_out(row).model_dump(mode="json"),
        }
    )


@router.post("/start")
def start_sync_service(request: Request) -> dict:
    result = _manager(request).start_service()
    payload = SyncServiceActionResult(**result)
    return success_response(data=payload.model_dump(), message="sync start requested")


@router.post("/stop")
def stop_sync_service(request: Request) -> dict:
    result = _manager(request).stop_service()
    payload = SyncServiceActionResult(**result)
    return success_response(data=payload.model_dump(), message="sync stop requested")


@router.post("/history")
def trigger_history_backfill(request: Request) -> dict:
    result = _manager(request).trigger_history_backfill()
    payload = SyncServiceActionResult(**result)
    return success_response(data=payload.model_dump(), message="history task requested")


@router.post("/recheck")
def trigger_recheck(request: Request) -> dict:
    result = _manager(request).trigger_recheck()
    payload = SyncServiceActionResult(**result)
    return success_response(data=payload.model_dump(), message="recheck task requested")

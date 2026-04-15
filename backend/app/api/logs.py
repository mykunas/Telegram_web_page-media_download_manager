from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.response import paginated_response, success_response
from app.models import ErrorLog, SystemLog
from app.schemas.log import ErrorLogOut, ErrorResolveOut, SystemLogOut

router = APIRouter(tags=["Logs"])


@router.get("/logs")
def list_system_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    level: str | None = Query(default=None),
    module: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(SystemLog)

    if level:
        query = query.filter(SystemLog.level == level.upper())

    if module:
        query = query.filter(SystemLog.module == module)

    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(SystemLog.message.ilike(pattern))

    if date_from is not None:
        query = query.filter(SystemLog.created_at >= date_from)

    if date_to is not None:
        inclusive_to = date_to + timedelta(days=1) if date_to.time() == datetime.min.time() else date_to
        query = query.filter(SystemLog.created_at < inclusive_to)

    total = query.count()
    rows = (
        query.order_by(SystemLog.created_at.desc(), SystemLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    data = [
        SystemLogOut(
            id=row.id,
            level=row.level,
            module=row.module,
            message=row.message,
            extra_json=row.extra_json,
            created_at=row.created_at,
        ).model_dump(mode="json")
        for row in rows
    ]

    return paginated_response(data, total=total, page=page, page_size=page_size)


@router.get("/errors")
def list_error_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    resolved: bool | None = Query(default=None),
    module: str | None = Query(default=None),
    chat_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(ErrorLog)

    if resolved is not None:
        query = query.filter(ErrorLog.resolved == resolved)

    if module:
        query = query.filter(ErrorLog.module == module)

    if chat_id is not None:
        query = query.filter(ErrorLog.chat_id == chat_id)

    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                ErrorLog.error_message.ilike(pattern),
                ErrorLog.error_type.ilike(pattern),
                ErrorLog.traceback.ilike(pattern),
                ErrorLog.file_path.ilike(pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(ErrorLog.created_at.desc(), ErrorLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    data = [
        ErrorLogOut(
            id=row.id,
            module=row.module,
            chat_id=row.chat_id,
            message_id=row.message_id,
            file_path=row.file_path,
            error_type=row.error_type,
            error_message=row.error_message,
            traceback=row.traceback,
            resolved=row.resolved,
            created_at=row.created_at,
        ).model_dump(mode="json")
        for row in rows
    ]

    return paginated_response(data, total=total, page=page, page_size=page_size)


@router.post("/errors/{error_id}/resolve")
def resolve_error_log(error_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(ErrorLog).filter(ErrorLog.id == error_id).first()
    if not row:
        raise AppException("error log not found", status_code=404)

    if not row.resolved:
        row.resolved = True
        db.commit()
        db.refresh(row)

    payload = ErrorResolveOut(id=row.id, resolved=row.resolved)
    return success_response(data=payload.model_dump(), message="resolved")


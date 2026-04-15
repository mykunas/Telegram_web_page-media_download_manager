from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import mimetypes
import os
import re
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi import Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AppException
from app.core.response import paginated_response, success_response
from app.models import DownloadRecord, DownloadStatus
from app.schemas.download import BatchRetryRequest, BatchRetryResult, DownloadRecordOut

router = APIRouter(prefix="/downloads", tags=["Downloads"])


VALID_RETRY_STATUSES = {DownloadStatus.FAILED}
MANUAL_REQUEUE_BLOCKED_STATUSES = {DownloadStatus.DOWNLOADING}
FILE_NAME_PATTERN = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})_(?P<chat_id>-?\d+)_(?P<message_id>\d+)_(?P<orig>.+)$"
)
THUMBNAIL_DIR = Path(os.getenv("THUMBNAIL_DIR", "/app/data/thumbnails"))
THUMBNAIL_SECONDS = os.getenv("THUMBNAIL_SECONDS", "3")
PREVIEW_VIDEO_DIR = Path(os.getenv("PREVIEW_VIDEO_DIR", "/app/data/preview_videos"))


def _apply_download_filters(
    query: SAQuery,
    *,
    status: str | None,
    chat_id: int | None,
    chat_name: str | None,
    media_type: str | None,
    keyword: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> SAQuery:
    if status:
        try:
            status_enum = DownloadStatus(status)
        except ValueError as exc:
            raise AppException(f"invalid status: {status}", status_code=400) from exc
        # Backward-compatible behavior for file listing pages:
        # when filtering by "success", include duplicate records that still point
        # to existing downloaded files.
        if status_enum == DownloadStatus.SUCCESS:
            query = query.filter(DownloadRecord.status.in_([DownloadStatus.SUCCESS, DownloadStatus.DUPLICATE]))
        else:
            query = query.filter(DownloadRecord.status == status_enum)

    if chat_id is not None:
        query = query.filter(DownloadRecord.chat_id == chat_id)

    if chat_name:
        query = query.filter(DownloadRecord.chat_name.ilike(f"%{chat_name}%"))

    if media_type:
        query = query.filter(DownloadRecord.media_type == media_type)

    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                DownloadRecord.original_file_name.ilike(pattern),
                DownloadRecord.saved_file_name.ilike(pattern),
            )
        )

    if date_from is not None:
        query = query.filter(DownloadRecord.created_at >= date_from)

    if date_to is not None:
        # include whole day when caller passes date-like time 00:00:00
        inclusive_to = date_to + timedelta(days=1) if date_to.time() == datetime.min.time() else date_to
        query = query.filter(DownloadRecord.created_at < inclusive_to)

    return query


def _to_download_out(row: DownloadRecord) -> DownloadRecordOut:
    return DownloadRecordOut(
        id=row.id,
        chat_id=row.chat_id,
        chat_name=row.chat_name,
        message_id=row.message_id,
        message_date=row.message_date,
        media_type=row.media_type,
        original_file_name=row.original_file_name,
        saved_file_name=row.saved_file_name,
        saved_path=row.saved_path,
        file_size=row.file_size,
        sha256=row.sha256,
        status=row.status.value if hasattr(row.status, "value") else str(row.status),
        source_type=row.source_type,
        retry_count=row.retry_count,
        error_message=row.error_message,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
    )


@router.get("")
def list_downloads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    status: str | None = Query(default=None),
    chat_id: int | None = Query(default=None),
    chat_name: str | None = Query(default=None),
    media_type: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    base_query = db.query(DownloadRecord).filter(
        or_(
            DownloadRecord.saved_file_name.is_(None),
            (
                ~DownloadRecord.saved_file_name.ilike("%.part%")
                & ~DownloadRecord.saved_file_name.ilike("%.temp%")
            ),
        )
    )
    filtered_query = _apply_download_filters(
        base_query,
        status=status,
        chat_id=chat_id,
        chat_name=chat_name,
        media_type=media_type,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
    )

    total = filtered_query.count()

    rows = (
        filtered_query.order_by(DownloadRecord.created_at.desc(), DownloadRecord.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    data = [_to_download_out(row).model_dump(mode="json") for row in rows]
    return paginated_response(data, total=total, page=page, page_size=page_size)


def _detect_media_type(file_path: Path) -> str:
    parts = {part.lower() for part in file_path.parts}
    if "videos" in parts:
        return "video"
    if "photos" in parts:
        return "photo"
    if "files" in parts:
        return "document"

    ext = file_path.suffix.lower()
    if ext in {".mp4", ".mkv", ".mov", ".avi", ".webm"}:
        return "video"
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return "photo"
    return "document"


def _calc_file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        while True:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _build_thumbnail_path(row: DownloadRecord, video_path: Path) -> Path:
    stat = video_path.stat()
    THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{row.id}_{int(stat.st_mtime)}_{stat.st_size}.jpg"
    return THUMBNAIL_DIR / key


def _generate_video_thumbnail(video_path: Path, thumbnail_path: Path) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        THUMBNAIL_SECONDS,
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        "scale=640:-1:force_original_aspect_ratio=decrease",
        "-q:v",
        "4",
        "-y",
        str(thumbnail_path),
    ]
    subprocess.run(cmd, check=True, timeout=30)


def _build_preview_video_path(row: DownloadRecord, source_path: Path) -> Path:
    stat = source_path.stat()
    PREVIEW_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    key = f"{row.id}_{int(stat.st_mtime)}_{stat.st_size}{source_path.suffix.lower()}"
    return PREVIEW_VIDEO_DIR / key


def _generate_preview_video(source_path: Path, preview_path: Path) -> None:
    # For mp4 files, move moov atom to file head so browser seek/progress drag works
    # without waiting for full file transfer.
    if source_path.suffix.lower() == ".mp4":
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source_path),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            "-y",
            str(preview_path),
        ]
        subprocess.run(cmd, check=True, timeout=120)
        return

    # Non-mp4 formats are served from original file directly.
    raise RuntimeError("preview optimization only supports mp4")


def _parse_range_header(range_header: str, file_size: int) -> tuple[int, int] | None:
    # Support only single range: bytes=start-end
    if not range_header or not range_header.startswith("bytes="):
        return None
    value = range_header.replace("bytes=", "", 1).strip()
    if "," in value or "-" not in value:
        return None

    start_raw, end_raw = value.split("-", 1)
    try:
        if start_raw == "":
            suffix_len = int(end_raw)
            if suffix_len <= 0:
                return None
            start = max(0, file_size - suffix_len)
            end = file_size - 1
        else:
            start = int(start_raw)
            end = int(end_raw) if end_raw else file_size - 1
    except ValueError:
        return None

    if start < 0 or end < 0 or start >= file_size:
        return None
    end = min(end, file_size - 1)
    if end < start:
        return None
    return start, end


def _iter_file_range(path: str, start: int, end: int, chunk_size: int = 1024 * 1024):
    with open(path, "rb") as file_obj:
        file_obj.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            data = file_obj.read(min(chunk_size, remaining))
            if not data:
                break
            remaining -= len(data)
            yield data


@router.post("/reconcile-files")
def reconcile_files_from_download_dir(
    root: str | None = Query(default=None, description="Custom root directory. Defaults to /downloads"),
    update_existing: bool = Query(default=True, description="Update existing DB records metadata"),
    with_hash: bool = Query(default=False, description="Calculate sha256 for imported files"),
    db: Session = Depends(get_db),
) -> dict:
    download_root = Path((root or "/downloads").strip() or "/downloads")
    if not download_root.exists() or not download_root.is_dir():
        raise AppException(f"download directory not found: {download_root}", status_code=400)

    existing_rows = db.query(DownloadRecord).all()
    existing_map: dict[tuple[int, int], DownloadRecord] = {
        (int(row.chat_id), int(row.message_id)): row for row in existing_rows
    }

    now = datetime.now(UTC)
    stats = {
        "root": str(download_root),
        "scanned_files": 0,
        "matched_files": 0,
        "inserted": 0,
        "updated": 0,
        "skipped_existing": 0,
        "skipped_name_unmatched": 0,
        "errors": 0,
        "hash_calculated": 0,
    }

    for file_path in download_root.rglob("*"):
        if not file_path.is_file():
            continue
        lower_name = file_path.name.lower()
        if lower_name.endswith(".part") or lower_name.endswith(".temp") or ".part." in lower_name:
            continue

        stats["scanned_files"] += 1
        match = FILE_NAME_PATTERN.match(file_path.name)
        if not match:
            stats["skipped_name_unmatched"] += 1
            continue

        stats["matched_files"] += 1
        try:
            chat_id = int(match.group("chat_id"))
            message_id = int(match.group("message_id"))
            rel = file_path.relative_to(download_root)
            chat_name = rel.parts[0] if rel.parts else ""
            file_size = int(file_path.stat().st_size)
            message_dt = datetime.strptime(match.group("ts"), "%Y-%m-%d_%H-%M-%S").replace(tzinfo=UTC)
            file_sha256 = _calc_file_sha256(file_path) if with_hash else None
            if with_hash:
                stats["hash_calculated"] += 1

            key = (chat_id, message_id)
            row = existing_map.get(key)
            if row is None:
                inserted = DownloadRecord(
                    chat_id=chat_id,
                    chat_name=chat_name,
                    message_id=message_id,
                    message_date=message_dt,
                    media_type=_detect_media_type(file_path),
                    original_file_name=match.group("orig"),
                    saved_file_name=file_path.name,
                    saved_path=str(file_path.resolve()),
                    file_size=file_size,
                    sha256=file_sha256,
                    status=DownloadStatus.SUCCESS,
                    source_type="filesystem_sync",
                    retry_count=0,
                    error_message=None,
                    created_at=now,
                    updated_at=now,
                    completed_at=now,
                )
                db.add(inserted)
                existing_map[key] = inserted
                stats["inserted"] += 1
                continue

            if not update_existing:
                stats["skipped_existing"] += 1
                continue

            row.chat_name = row.chat_name or chat_name
            row.message_date = row.message_date or message_dt
            row.media_type = row.media_type or _detect_media_type(file_path)
            row.original_file_name = row.original_file_name or match.group("orig")
            row.saved_file_name = file_path.name
            row.saved_path = str(file_path.resolve())
            row.file_size = file_size
            if with_hash:
                row.sha256 = file_sha256

            if row.status not in {DownloadStatus.SUCCESS, DownloadStatus.DUPLICATE}:
                row.status = DownloadStatus.SUCCESS
                row.error_message = None
                row.completed_at = now
            elif row.completed_at is None:
                row.completed_at = now

            row.source_type = row.source_type or "filesystem_sync"
            row.updated_at = now
            stats["updated"] += 1
        except Exception:
            stats["errors"] += 1

    db.commit()
    return success_response(data=stats, message="reconcile completed")


@router.get("/{record_id}/thumbnail")
def download_record_thumbnail(record_id: int, db: Session = Depends(get_db)):
    row = db.query(DownloadRecord).filter(DownloadRecord.id == record_id).first()
    if not row:
        raise AppException("download record not found", status_code=404)

    if (row.media_type or "").lower() != "video":
        raise AppException("thumbnail is only available for video", status_code=400)

    file_path = (row.saved_path or "").strip()
    if not file_path:
        raise AppException("file path is empty", status_code=404)

    video_path = Path(file_path)
    if not video_path.exists() or not video_path.is_file():
        raise AppException("file not found on disk", status_code=404)

    thumbnail_path = _build_thumbnail_path(row, video_path)
    if not thumbnail_path.exists():
        try:
            _generate_video_thumbnail(video_path, thumbnail_path)
        except Exception as exc:
            raise AppException(f"failed to generate thumbnail: {exc}", status_code=500) from exc

    return FileResponse(
        path=str(thumbnail_path),
        media_type="image/jpeg",
        filename=thumbnail_path.name,
    )


@router.get("/{record_id}")
def get_download_detail(record_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(DownloadRecord).filter(DownloadRecord.id == record_id).first()
    if not row:
        raise AppException("download record not found", status_code=404)

    return success_response(data=_to_download_out(row).model_dump(mode="json"))


@router.post("/{record_id}/retry")
def retry_download_record(record_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(DownloadRecord).filter(DownloadRecord.id == record_id).first()
    if not row:
        raise AppException("download record not found", status_code=404)

    if row.status not in VALID_RETRY_STATUSES:
        current = row.status.value if hasattr(row.status, "value") else str(row.status)
        raise AppException(f"only failed record can be retried, current status: {current}", status_code=400)

    row.status = DownloadStatus.WAITING
    row.error_message = None
    row.completed_at = None
    row.updated_at = datetime.now(UTC)
    row.retry_count = 0
    db.commit()
    db.refresh(row)

    return success_response(data=_to_download_out(row).model_dump(mode="json"), message="retry queued")


@router.post("/{record_id}/manual-download")
def manual_download_record(record_id: int, db: Session = Depends(get_db)) -> dict:
    row = db.query(DownloadRecord).filter(DownloadRecord.id == record_id).first()
    if not row:
        raise AppException("download record not found", status_code=404)

    if row.status in MANUAL_REQUEUE_BLOCKED_STATUSES:
        current = row.status.value if hasattr(row.status, "value") else str(row.status)
        raise AppException(f"record is downloading, current status: {current}", status_code=400)

    row.status = DownloadStatus.WAITING
    row.source_type = "manual"
    row.error_message = None
    row.completed_at = None
    row.updated_at = datetime.now(UTC)
    row.retry_count = 0
    db.commit()
    db.refresh(row)

    return success_response(data=_to_download_out(row).model_dump(mode="json"), message="manual download queued")


@router.post("/batch-retry")
def batch_retry_download_records(payload: BatchRetryRequest, db: Session = Depends(get_db)) -> dict:
    query = db.query(DownloadRecord).filter(DownloadRecord.status == DownloadStatus.FAILED)

    if payload.ids:
        query = query.filter(DownloadRecord.id.in_(payload.ids))

    rows = query.all()
    if not rows:
        result = BatchRetryResult(retried_count=0, retried_ids=[])
        return success_response(data=result.model_dump(), message="no failed records to retry")

    now = datetime.now(UTC)
    retried_ids: list[int] = []
    for row in rows:
        row.status = DownloadStatus.WAITING
        row.error_message = None
        row.completed_at = None
        row.updated_at = now
        row.retry_count = 0
        retried_ids.append(row.id)

    db.commit()

    result = BatchRetryResult(retried_count=len(retried_ids), retried_ids=retried_ids)
    return success_response(data=result.model_dump(), message="batch retry queued")


@router.get("/{record_id}/file")
def download_record_file(
    record_id: int,
    request: Request,
    mode: str = Query(default="download", pattern="^(download|inline)$"),
    db: Session = Depends(get_db),
):
    row = db.query(DownloadRecord).filter(DownloadRecord.id == record_id).first()
    if not row:
        raise AppException("download record not found", status_code=404)

    file_path = (row.saved_path or "").strip()
    if not file_path:
        raise AppException("file path is empty", status_code=404)

    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        raise AppException("file not found on disk", status_code=404)

    media_type, _ = mimetypes.guess_type(file_path)
    media_type = media_type or "application/octet-stream"
    filename = row.saved_file_name or row.original_file_name or os.path.basename(file_path)
    serve_path = file_path

    if mode == "inline" and (row.media_type or "").lower() == "video":
        source_path = Path(file_path)
        if source_path.suffix.lower() == ".mp4":
            try:
                preview_path = _build_preview_video_path(row, source_path)
                if not preview_path.exists():
                    _generate_preview_video(source_path, preview_path)
                serve_path = str(preview_path)
            except Exception:
                serve_path = file_path

    headers = {"Accept-Ranges": "bytes"}
    if mode == "inline":
        headers["Content-Disposition"] = "inline"

    if mode == "inline":
        file_size = os.path.getsize(serve_path)
        range_header = request.headers.get("range", "")
        parsed = _parse_range_header(range_header, file_size)
        if range_header and parsed is None:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})
        if parsed is not None:
            start, end = parsed
            content_length = end - start + 1
            partial_headers = {
                **headers,
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
            }
            return StreamingResponse(
                _iter_file_range(serve_path, start, end),
                status_code=206,
                media_type=media_type,
                headers=partial_headers,
            )

    return FileResponse(
        path=serve_path,
        media_type=media_type,
        filename=filename if mode == "download" else None,
        headers=headers,
    )

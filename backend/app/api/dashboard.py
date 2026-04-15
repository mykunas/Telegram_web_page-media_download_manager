from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success_response
from app.models import ChannelConfig, DownloadRecord, DownloadStatus, SyncStatus
from app.schemas.dashboard import (
    DashboardChannelStatItem,
    DashboardCpuStats,
    DashboardMemoryStats,
    DashboardNetworkStats,
    DashboardSummaryData,
    DashboardSystemStatsData,
    DashboardTrendItem,
    DashboardActiveDownloadItem,
    DashboardActiveDownloadsData,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@dataclass
class _NetSnapshot:
    ts: float
    rx_bytes: int
    tx_bytes: int


@dataclass
class _CpuSnapshot:
    ts: float
    total: int
    idle: int


_stats_lock = Lock()
_last_net_snapshot: _NetSnapshot | None = None
_last_cpu_snapshot: _CpuSnapshot | None = None
_last_download_snapshot: dict[int, tuple[float, int]] = {}


def _safe_read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _read_cpu_totals() -> tuple[int, int]:
    text = _safe_read_text("/proc/stat")
    for line in text.splitlines():
        if not line.startswith("cpu "):
            continue
        parts = line.split()
        if len(parts) < 8:
            break
        user, nice, system, idle, iowait, irq, softirq, steal = [int(x) for x in parts[1:9]]
        total = user + nice + system + idle + iowait + irq + softirq + steal
        idle_total = idle + iowait
        return total, idle_total
    return 0, 0


def _read_net_totals() -> tuple[int, int]:
    text = _safe_read_text("/proc/net/dev")
    rx_sum = 0
    tx_sum = 0
    for line in text.splitlines():
        if ":" not in line:
            continue
        iface, payload = [x.strip() for x in line.split(":", 1)]
        if iface == "lo":
            continue
        cols = payload.split()
        if len(cols) < 16:
            continue
        rx_sum += int(cols[0])
        tx_sum += int(cols[8])
    return rx_sum, tx_sum


def _read_meminfo() -> dict[str, int]:
    result: dict[str, int] = {}
    text = _safe_read_text("/proc/meminfo")
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, raw = [x.strip() for x in line.split(":", 1)]
        parts = raw.split()
        if not parts:
            continue
        try:
            result[key] = int(parts[0]) * 1024
        except ValueError:
            continue
    return result


def _read_loadavg() -> tuple[float, float, float]:
    text = _safe_read_text("/proc/loadavg").strip()
    if not text:
        return 0.0, 0.0, 0.0
    parts = text.split()
    if len(parts) < 3:
        return 0.0, 0.0, 0.0
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return 0.0, 0.0, 0.0


def _collect_system_stats() -> DashboardSystemStatsData:
    global _last_cpu_snapshot, _last_net_snapshot

    now = monotonic()
    cpu_total, cpu_idle = _read_cpu_totals()
    rx_total, tx_total = _read_net_totals()
    load_1, load_5, load_15 = _read_loadavg()
    mem = _read_meminfo()

    try:
        import os

        cores = int(os.cpu_count() or 0)
    except Exception:
        cores = 0

    with _stats_lock:
        cpu_usage = 0.0
        if _last_cpu_snapshot is not None and cpu_total > _last_cpu_snapshot.total:
            total_delta = cpu_total - _last_cpu_snapshot.total
            idle_delta = cpu_idle - _last_cpu_snapshot.idle
            if total_delta > 0:
                cpu_usage = max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100))
        _last_cpu_snapshot = _CpuSnapshot(ts=now, total=cpu_total, idle=cpu_idle)

        rx_speed = 0.0
        tx_speed = 0.0
        if _last_net_snapshot is not None and now > _last_net_snapshot.ts:
            sec = now - _last_net_snapshot.ts
            if sec > 0:
                rx_speed = max(0.0, (rx_total - _last_net_snapshot.rx_bytes) / sec)
                tx_speed = max(0.0, (tx_total - _last_net_snapshot.tx_bytes) / sec)
        _last_net_snapshot = _NetSnapshot(ts=now, rx_bytes=rx_total, tx_bytes=tx_total)

    mem_total = int(mem.get("MemTotal", 0))
    mem_available = int(mem.get("MemAvailable", 0))
    mem_used = max(0, mem_total - mem_available)
    mem_usage = (mem_used / mem_total * 100) if mem_total > 0 else 0.0

    swap_total = int(mem.get("SwapTotal", 0))
    swap_free = int(mem.get("SwapFree", 0))
    swap_used = max(0, swap_total - swap_free)

    return DashboardSystemStatsData(
        cpu=DashboardCpuStats(
            usage_percent=round(cpu_usage, 2),
            cores_logical=cores,
            load_avg_1m=round(load_1, 2),
            load_avg_5m=round(load_5, 2),
            load_avg_15m=round(load_15, 2),
        ),
        memory=DashboardMemoryStats(
            total_bytes=mem_total,
            used_bytes=mem_used,
            available_bytes=mem_available,
            usage_percent=round(mem_usage, 2),
            swap_total_bytes=swap_total,
            swap_used_bytes=swap_used,
        ),
        network=DashboardNetworkStats(
            rx_bytes_per_sec=round(rx_speed, 2),
            tx_bytes_per_sec=round(tx_speed, 2),
            rx_total_bytes=rx_total,
            tx_total_bytes=tx_total,
        ),
    )


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    now = datetime.now(UTC)
    since_24h = now - timedelta(hours=24)

    running_sync_count = (
        db.query(func.count(SyncStatus.id))
        .filter(SyncStatus.sync_status.in_(["running", "scanning_history"]))
        .scalar()
        or 0
    )
    service_status = "running" if running_sync_count > 0 else "idle"

    configured_channel_count = db.query(func.count(ChannelConfig.id)).scalar() or 0
    total_download_files = db.query(func.count(DownloadRecord.id)).scalar() or 0

    total_success = (
        db.query(func.count(DownloadRecord.id))
        .filter(DownloadRecord.status == DownloadStatus.SUCCESS)
        .scalar()
        or 0
    )
    total_failed = (
        db.query(func.count(DownloadRecord.id))
        .filter(DownloadRecord.status == DownloadStatus.FAILED)
        .scalar()
        or 0
    )
    total_skipped = (
        db.query(func.count(DownloadRecord.id))
        .filter(DownloadRecord.status.in_([DownloadStatus.SKIPPED, DownloadStatus.DUPLICATE]))
        .scalar()
        or 0
    )

    total_size_bytes = (
        db.query(func.coalesce(func.sum(DownloadRecord.file_size), 0))
        .filter(DownloadRecord.status == DownloadStatus.SUCCESS)
        .scalar()
        or 0
    )

    downloaded_last_24h = (
        db.query(func.count(DownloadRecord.id))
        .filter(
            DownloadRecord.status == DownloadStatus.SUCCESS,
            DownloadRecord.completed_at.isnot(None),
            DownloadRecord.completed_at >= since_24h,
        )
        .scalar()
        or 0
    )

    payload = DashboardSummaryData(
        service_status=service_status,
        configured_channel_count=configured_channel_count,
        total_download_files=total_download_files,
        total_success=total_success,
        total_failed=total_failed,
        total_skipped=total_skipped,
        total_size_bytes=int(total_size_bytes),
        downloaded_last_24h=downloaded_last_24h,
    )

    return success_response(data=payload.model_dump())


@router.get("/trend")
def dashboard_trend(db: Session = Depends(get_db)) -> dict:
    today = datetime.now(UTC).date()
    start_day = today - timedelta(days=6)
    start_dt = datetime.combine(start_day, datetime.min.time(), tzinfo=UTC)

    rows = (
        db.query(
            func.date(DownloadRecord.created_at).label("day"),
            func.count(DownloadRecord.id).label("total"),
            func.sum(case((DownloadRecord.status == DownloadStatus.SUCCESS, 1), else_=0)).label("success"),
            func.sum(case((DownloadRecord.status == DownloadStatus.FAILED, 1), else_=0)).label("failed"),
            func.sum(
                case(
                    (DownloadRecord.status.in_([DownloadStatus.SKIPPED, DownloadStatus.DUPLICATE]), 1),
                    else_=0,
                )
            ).label("skipped"),
        )
        .filter(DownloadRecord.created_at >= start_dt)
        .group_by(func.date(DownloadRecord.created_at))
        .order_by(func.date(DownloadRecord.created_at))
        .all()
    )

    row_map = {
        str(row.day): {
            "total": int(row.total or 0),
            "success": int(row.success or 0),
            "failed": int(row.failed or 0),
            "skipped": int(row.skipped or 0),
        }
        for row in rows
    }

    result: list[dict] = []
    for i in range(7):
        current_day = start_day + timedelta(days=i)
        key = current_day.isoformat()
        item = row_map.get(key, {"total": 0, "success": 0, "failed": 0, "skipped": 0})
        result.append(
            DashboardTrendItem(
                day=current_day,
                total=item["total"],
                success=item["success"],
                failed=item["failed"],
                skipped=item["skipped"],
            ).model_dump(mode="json")
        )

    return success_response(data=result)


@router.get("/channel-stats")
def dashboard_channel_stats(db: Session = Depends(get_db)) -> dict:
    rows = (
        db.query(
            DownloadRecord.chat_id.label("chat_id"),
            func.max(DownloadRecord.chat_name).label("chat_name"),
            func.count(DownloadRecord.id).label("total"),
            func.sum(case((DownloadRecord.status == DownloadStatus.SUCCESS, 1), else_=0)).label("success"),
            func.sum(case((DownloadRecord.status == DownloadStatus.FAILED, 1), else_=0)).label("failed"),
            func.sum(
                case(
                    (DownloadRecord.status.in_([DownloadStatus.SKIPPED, DownloadStatus.DUPLICATE]), 1),
                    else_=0,
                )
            ).label("skipped"),
            func.coalesce(
                func.sum(
                    case(
                        (DownloadRecord.status == DownloadStatus.SUCCESS, DownloadRecord.file_size),
                        else_=0,
                    )
                ),
                0,
            ).label("total_size_bytes"),
        )
        .group_by(DownloadRecord.chat_id)
        .order_by(func.count(DownloadRecord.id).desc())
        .all()
    )

    result = [
        DashboardChannelStatItem(
            chat_id=int(row.chat_id),
            chat_name=row.chat_name,
            total=int(row.total or 0),
            success=int(row.success or 0),
            failed=int(row.failed or 0),
            skipped=int(row.skipped or 0),
            total_size_bytes=int(row.total_size_bytes or 0),
        ).model_dump()
        for row in rows
    ]

    return success_response(data=result)


@router.get("/system-stats")
def dashboard_system_stats() -> dict:
    payload = _collect_system_stats()
    return success_response(data=payload.model_dump())


@router.get("/active-downloads")
def dashboard_active_downloads(db: Session = Depends(get_db)) -> dict:
    now = monotonic()

    downloading_rows = (
        db.query(DownloadRecord)
        .filter(DownloadRecord.status == DownloadStatus.DOWNLOADING)
        .order_by(DownloadRecord.updated_at.desc(), DownloadRecord.id.desc())
        .limit(20)
        .all()
    )
    waiting_count = (
        db.query(func.count(DownloadRecord.id))
        .filter(DownloadRecord.status == DownloadStatus.WAITING)
        .scalar()
        or 0
    )

    items: list[dict] = []
    active_ids: set[int] = set()
    with _stats_lock:
        for row in downloading_rows:
            active_ids.add(int(row.id))
            path = (row.saved_path or "").strip()
            current_bytes = 0
            if path:
                try:
                    p = Path(path)
                    if p.exists() and p.is_file():
                        current_bytes = int(p.stat().st_size)
                    elif p.suffix == ".part":
                        temp_p = Path(f"{path}.temp")
                        if temp_p.exists() and temp_p.is_file():
                            current_bytes = int(temp_p.stat().st_size)
                except Exception:
                    current_bytes = 0

            total_bytes = int(row.file_size or 0)
            progress = 0.0
            if total_bytes > 0:
                progress = max(0.0, min(100.0, current_bytes * 100.0 / total_bytes))

            speed = 0.0
            last = _last_download_snapshot.get(int(row.id))
            if last is not None:
                last_ts, last_bytes = last
                dt = now - last_ts
                if dt > 0 and current_bytes >= last_bytes:
                    speed = (current_bytes - last_bytes) / dt
            _last_download_snapshot[int(row.id)] = (now, current_bytes)

            items.append(
                DashboardActiveDownloadItem(
                    id=int(row.id),
                    chat_name=row.chat_name,
                    file_name=row.saved_file_name or row.original_file_name or f"record_{row.id}",
                    media_type=row.media_type,
                    status=(row.status.value if hasattr(row.status, "value") else str(row.status)),
                    current_bytes=current_bytes,
                    total_bytes=total_bytes,
                    progress_percent=round(progress, 2),
                    speed_bytes_per_sec=round(speed, 2),
                    saved_path=row.saved_path,
                ).model_dump()
            )

        stale_ids = [rid for rid in _last_download_snapshot.keys() if rid not in active_ids]
        for rid in stale_ids:
            _last_download_snapshot.pop(rid, None)

    payload = DashboardActiveDownloadsData(
        downloading_count=len(downloading_rows),
        waiting_count=int(waiting_count),
        download_speed_bytes_per_sec=round(
            sum(float(item.get("speed_bytes_per_sec") or 0.0) for item in items),
            2,
        ),
        downloaded_bytes_active=int(sum(int(item.get("current_bytes") or 0) for item in items)),
        download_total_bytes_active=int(sum(int(item.get("total_bytes") or 0) for item in items)),
        items=items,
    )
    return success_response(data=payload.model_dump())

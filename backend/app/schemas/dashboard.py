from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class DashboardSummaryData(BaseModel):
    service_status: str = Field(description="Current downloader service status")
    configured_channel_count: int
    total_download_files: int
    total_success: int
    total_failed: int
    total_skipped: int
    total_size_bytes: int
    downloaded_last_24h: int


class DashboardTrendItem(BaseModel):
    day: date
    total: int
    success: int
    failed: int
    skipped: int


class DashboardChannelStatItem(BaseModel):
    chat_id: int
    chat_name: str | None
    total: int
    success: int
    failed: int
    skipped: int
    total_size_bytes: int


class DashboardCpuStats(BaseModel):
    usage_percent: float
    cores_logical: int
    load_avg_1m: float
    load_avg_5m: float
    load_avg_15m: float


class DashboardMemoryStats(BaseModel):
    total_bytes: int
    used_bytes: int
    available_bytes: int
    usage_percent: float
    swap_total_bytes: int
    swap_used_bytes: int


class DashboardNetworkStats(BaseModel):
    rx_bytes_per_sec: float
    tx_bytes_per_sec: float
    rx_total_bytes: int
    tx_total_bytes: int


class DashboardSystemStatsData(BaseModel):
    cpu: DashboardCpuStats
    memory: DashboardMemoryStats
    network: DashboardNetworkStats


class DashboardActiveDownloadItem(BaseModel):
    id: int
    chat_name: str | None
    file_name: str
    media_type: str | None
    status: str
    current_bytes: int
    total_bytes: int
    progress_percent: float
    speed_bytes_per_sec: float
    saved_path: str | None


class DashboardActiveDownloadsData(BaseModel):
    downloading_count: int
    waiting_count: int
    download_speed_bytes_per_sec: float
    downloaded_bytes_active: int
    download_total_bytes_active: int
    items: list[DashboardActiveDownloadItem]

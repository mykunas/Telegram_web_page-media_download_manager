from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SyncStatus(Base):
    __tablename__ = "sync_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    last_scanned_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_downloaded_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    total_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_success: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sync_status: Mapped[str] = mapped_column(String(32), nullable=False, default="idle")
    last_sync_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, server_default=func.now())

from sqlalchemy import BigInteger, DateTime, Enum, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import DownloadStatus


class DownloadRecord(Base):
    __tablename__ = "download_records"
    __table_args__ = (
        UniqueConstraint("chat_id", "message_id", name="uq_download_record_chat_message"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    chat_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message_date: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    media_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    original_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    saved_file_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    saved_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[DownloadStatus] = mapped_column(
        Enum(DownloadStatus, name="download_status", native_enum=False, create_constraint=True),
        nullable=False,
        default=DownloadStatus.WAITING,
        index=True,
    )
    source_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

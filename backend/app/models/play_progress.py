from sqlalchemy import Boolean, DateTime, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PlayProgress(Base):
    __tablename__ = "play_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "record_id", name="uq_play_progress_user_record"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    last_position_sec: Mapped[float] = mapped_column(nullable=False, default=0.0)
    duration_sec: Mapped[float] = mapped_column(nullable=False, default=0.0)
    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


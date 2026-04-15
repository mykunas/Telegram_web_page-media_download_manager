from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserPreferenceProfile(Base):
    __tablename__ = "user_preference_profile"
    __table_args__ = (
        UniqueConstraint("user_id", "channel", "media_type", "tag", name="uq_user_preference_profile_dim"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    channel: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    media_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    tag: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

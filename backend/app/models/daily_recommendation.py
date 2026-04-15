from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DailyRecommendation(Base):
    __tablename__ = "daily_recommendations"
    __table_args__ = (
        UniqueConstraint("rec_date", "user_id", "record_id", name="uq_daily_recommendation_user_record"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    rec_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


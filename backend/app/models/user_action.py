from sqlalchemy import BigInteger, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserAction(Base):
    __tablename__ = "user_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    record_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


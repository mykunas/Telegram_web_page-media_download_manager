from sqlalchemy import DateTime, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserCollectionItem(Base):
    __tablename__ = "user_collection_items"
    __table_args__ = (
        UniqueConstraint("user_id", "collection_id", "record_id", name="uq_user_collection_item_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    collection_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

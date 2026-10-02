from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    __table_args__ = (UniqueConstraint("user_id", "path", name="uq_saved_search_path"),)

    alerts_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    alerts_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(60))
    path: Mapped[str] = mapped_column(String(2000))

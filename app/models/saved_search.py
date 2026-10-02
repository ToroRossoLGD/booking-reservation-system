from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedSearch(Base):
    __tablename__ = "saved_searches"
    __table_args__ = (UniqueConstraint("user_id", "path", name="uq_saved_search_path"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(60))
    path: Mapped[str] = mapped_column(String(2000))

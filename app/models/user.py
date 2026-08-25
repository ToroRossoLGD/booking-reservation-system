import enum

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    CUSTOMER = "customer"
    OWNER = "owner"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    google_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=UserRole.CUSTOMER.value,
    )
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    venues = relationship(
        "Venue",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

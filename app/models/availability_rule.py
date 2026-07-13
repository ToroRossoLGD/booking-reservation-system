from datetime import time

from sqlalchemy import ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"

    __table_args__ = (
        UniqueConstraint(
            "resource_id",
            "weekday",
            "start_time",
            "end_time",
            name="uq_availability_rule_interval",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    resource_id: Mapped[int] = mapped_column(
        ForeignKey(
            "resources.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    weekday: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    start_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

    end_time: Mapped[time] = mapped_column(
        Time,
        nullable=False,
    )

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.cache import delete_available_slots_cache_for_resource
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.reservation import Reservation, ReservationStatus
from app.services.reservation_service import ReservationService
from app.tasks.celery_app import celery_app


@celery_app.task(name="expire_pending_reservations_task")
def expire_pending_reservations_task() -> dict:
    return asyncio.run(_expire_pending_reservations())


async def _expire_pending_reservations() -> dict:
    cutoff_time = datetime.now(UTC) - timedelta(
        minutes=settings.RESERVATION_EXPIRE_MINUTES
    )

    expired_count = 0

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Reservation).where(
                Reservation.status == ReservationStatus.PENDING.value,
                Reservation.created_at < cutoff_time,
            )
        )

        reservations = list(result.scalars().all())

        for reservation in reservations:
            reservation.status = ReservationStatus.EXPIRED.value
            expired_count += 1

            await delete_available_slots_cache_for_resource(reservation.resource_id)

        await db.commit()

    return {"expired_count": expired_count}


@celery_app.task(name="mark_reservation_no_shows_task")
def mark_reservation_no_shows_task() -> dict:
    return asyncio.run(_mark_reservation_no_shows())


async def _mark_reservation_no_shows() -> dict:
    async with AsyncSessionLocal() as db:
        return await ReservationService(db).mark_no_shows()

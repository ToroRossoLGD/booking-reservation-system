import asyncio

from app.db.session import AsyncSessionLocal
from app.services.reservation_service import ReservationService
from app.tasks.celery_app import celery_app


@celery_app.task(name="expire_pending_reservations_task")
def expire_pending_reservations_task() -> dict:
    return asyncio.run(_expire_pending_reservations())


async def _expire_pending_reservations() -> dict:
    async with AsyncSessionLocal() as db:
        return await ReservationService(db).expire_pending_reservations()


@celery_app.task(name="mark_reservation_no_shows_task")
def mark_reservation_no_shows_task() -> dict:
    return asyncio.run(_mark_reservation_no_shows())


async def _mark_reservation_no_shows() -> dict:
    async with AsyncSessionLocal() as db:
        return await ReservationService(db).mark_no_shows()

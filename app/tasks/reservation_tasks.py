import asyncio

from app.db.session import AsyncSessionLocal
from app.services.reservation_reminder_service import ReservationReminderService
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


@celery_app.task(name="send_reservation_reminders_task")
def send_reservation_reminders_task() -> dict:
    return asyncio.run(_send_reservation_reminders())


async def _send_reservation_reminders() -> dict:
    async with AsyncSessionLocal() as db:
        return await ReservationReminderService(db).send_due_reminders()

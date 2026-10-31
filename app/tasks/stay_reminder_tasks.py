import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.services.stay_reminder_service import run_stay_reminders
from app.tasks.celery_app import celery_app


async def process_stay_reminders():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        return await run_stay_reminders(
            async_sessionmaker(engine, expire_on_commit=False)
        )
    finally:
        await engine.dispose()


@celery_app.task(name="send_stay_reminders", soft_time_limit=240, time_limit=270)
def send_stay_reminders():
    return asyncio.run(process_stay_reminders())

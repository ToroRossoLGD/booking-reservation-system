import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.services.viewing_reminder_service import run_viewing_reminders
from app.tasks.celery_app import celery_app


async def process_viewing_reminders():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        return await run_viewing_reminders(
            async_sessionmaker(engine, expire_on_commit=False)
        )
    finally:
        await engine.dispose()


@celery_app.task(name="send_viewing_reminders", soft_time_limit=240, time_limit=270)
def send_viewing_reminders():
    return asyncio.run(process_viewing_reminders())

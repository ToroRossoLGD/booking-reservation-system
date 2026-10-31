import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.services.occupancy_sync_service import run_calendar_syncs
from app.tasks.celery_app import celery_app


async def process_calendars():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        return await run_calendar_syncs(
            async_sessionmaker(engine, expire_on_commit=False)
        )
    finally:
        await engine.dispose()


@celery_app.task(
    name="refresh_occupancy_calendars", soft_time_limit=240, time_limit=270
)
def refresh_occupancy_calendars():
    return asyncio.run(process_calendars())

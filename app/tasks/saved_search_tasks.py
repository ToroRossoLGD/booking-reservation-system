import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.services.saved_search_alert_service import run_saved_search_alerts
from app.tasks.celery_app import celery_app


async def process_alerts():
    # Celery invokes asyncio.run repeatedly; do not reuse connections across loops.
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        return await run_saved_search_alerts(sessions)
    finally:
        await engine.dispose()


@celery_app.task(name="send_saved_search_alerts_task")
def send_saved_search_alerts_task():
    return asyncio.run(process_alerts())

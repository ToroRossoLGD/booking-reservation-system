import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.services.property_email_digest_service import run_email_digests
from app.tasks.celery_app import celery_app


async def process_email_digests():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        return await run_email_digests(
            async_sessionmaker(engine, expire_on_commit=False)
        )
    finally:
        await engine.dispose()


@celery_app.task(
    name="send_property_email_digests", soft_time_limit=240, time_limit=270
)
def send_property_email_digests():
    return asyncio.run(process_email_digests())

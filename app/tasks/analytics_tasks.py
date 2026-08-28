import asyncio

from app.db.session import AsyncSessionLocal
from app.services.analytics_pipeline_service import AnalyticsPipelineService
from app.tasks.celery_app import celery_app


@celery_app.task(name="refresh_daily_analytics_task")
def refresh_daily_analytics_task() -> dict:
    return asyncio.run(_refresh_daily_analytics())


async def _refresh_daily_analytics() -> dict:
    async with AsyncSessionLocal() as db:
        result = await AnalyticsPipelineService(db).refresh_yesterday()
        return result.model_dump(mode="json")

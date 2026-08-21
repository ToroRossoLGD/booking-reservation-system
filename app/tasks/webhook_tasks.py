import asyncio

from app.db.session import AsyncSessionLocal
from app.services.webhook_service import WebhookService
from app.tasks.celery_app import celery_app


@celery_app.task(name="deliver_due_webhooks_task")
def deliver_due_webhooks_task() -> dict:
    return asyncio.run(_deliver_due_webhooks())


async def _deliver_due_webhooks() -> dict:
    async with AsyncSessionLocal() as db:
        return await WebhookService(db).deliver_due()

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.models.webhook import WebhookDeliveryStatus, WebhookSubscription
from app.repositories.venue_repository import VenueRepository
from app.repositories.webhook_repository import WebhookRepository
from app.schemas.webhook import WebhookCreate, WebhookUpdate


class WebhookService:
    def __init__(self, db: AsyncSession):
        self.repository = WebhookRepository(db)
        self.venue_repository = VenueRepository(db)

    def _secret(self, signing_key: str) -> str:
        digest = hmac.new(
            settings.JWT_SECRET.encode(), signing_key.encode(), hashlib.sha256
        ).digest()
        return base64.urlsafe_b64encode(digest).decode().rstrip("=")

    async def _authorize(self, venue_id: int, user: User) -> None:
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(status_code=404, detail="Venue not found")
        if user.role != "admin" and venue.owner_id != user.id:
            raise HTTPException(
                status_code=403,
                detail="You can manage webhooks only for your own venues",
            )

    async def create(self, venue_id: int, data: WebhookCreate, user: User) -> dict:
        await self._authorize(venue_id, user)
        if (
            await self.repository.count_active(venue_id)
            >= settings.MAX_ACTIVE_VENUE_WEBHOOKS
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "A venue can have at most "
                    f"{settings.MAX_ACTIVE_VENUE_WEBHOOKS} active webhooks"
                ),
            )
        now = datetime.now(UTC)
        item = await self.repository.create(
            WebhookSubscription(
                venue_id=venue_id,
                name=data.name,
                target_url=str(data.target_url),
                event_types=list(data.event_types),
                signing_key=secrets.token_hex(18),
                created_by_id=user.id,
                created_at=now,
                updated_at=now,
            )
        )
        return {**item.__dict__, "signing_secret": self._secret(item.signing_key)}

    async def list(self, venue_id: int, user: User):
        await self._authorize(venue_id, user)
        return await self.repository.list_for_venue(venue_id)

    async def update(
        self, venue_id: int, subscription_id: int, data: WebhookUpdate, user: User
    ):
        await self._authorize(venue_id, user)
        item = await self.repository.get_for_venue(subscription_id, venue_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Webhook not found")
        if (
            data.is_active
            and not item.is_active
            and await self.repository.count_active(venue_id)
            >= settings.MAX_ACTIVE_VENUE_WEBHOOKS
        ):
            raise HTTPException(status_code=409, detail="Active webhook limit reached")
        item.name = data.name
        item.target_url = str(data.target_url)
        item.event_types = list(data.event_types)
        item.is_active = data.is_active
        item.updated_at = datetime.now(UTC)
        return await self.repository.update(item)

    async def deactivate(self, venue_id: int, subscription_id: int, user: User):
        await self._authorize(venue_id, user)
        item = await self.repository.get_for_venue(subscription_id, venue_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Webhook not found")
        item.is_active = False
        item.updated_at = datetime.now(UTC)
        return await self.repository.update(item)

    async def list_deliveries(self, venue_id: int, user: User):
        await self._authorize(venue_id, user)
        return await self.repository.list_deliveries(venue_id)

    async def retry(self, venue_id: int, delivery_id: int, user: User):
        await self._authorize(venue_id, user)
        item = await self.repository.get_delivery_for_venue(delivery_id, venue_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Webhook delivery not found")
        if item.status == WebhookDeliveryStatus.DELIVERED.value:
            raise HTTPException(
                status_code=409, detail="A delivered webhook cannot be retried"
            )
        item.status = WebhookDeliveryStatus.PENDING.value
        item.attempts = 0
        item.next_attempt_at = datetime.now(UTC)
        item.response_status = None
        item.last_error = None
        item.delivered_at = None
        await self.repository.save_delivery(item)
        return item

    async def deliver_due(
        self, current_time: datetime | None = None, limit: int = 100
    ) -> dict:
        now = current_time or datetime.now(UTC)
        deliveries = await self.repository.get_due_deliveries(now, limit)
        delivered = failed = retrying = 0
        async with httpx.AsyncClient(
            timeout=settings.WEBHOOK_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            for item in deliveries:
                subscription = await self.repository.get_subscription(
                    item.subscription_id
                )
                if subscription is None or not subscription.is_active:
                    item.status = WebhookDeliveryStatus.FAILED.value
                    item.last_error = "Webhook subscription is inactive"
                    failed += 1
                    await self.repository.save_delivery(item)
                    continue
                body = json.dumps(
                    item.payload, separators=(",", ":"), sort_keys=True
                ).encode()
                timestamp = str(int(now.timestamp()))
                signature = hmac.new(
                    self._secret(subscription.signing_key).encode(),
                    timestamp.encode() + b"." + body,
                    hashlib.sha256,
                ).hexdigest()
                item.attempts += 1
                item.updated_at = now
                try:
                    response = await client.post(
                        subscription.target_url,
                        content=body,
                        headers={
                            "Content-Type": "application/json",
                            "X-Webhook-ID": str(item.id),
                            "X-Webhook-Timestamp": timestamp,
                            "X-Webhook-Signature": f"sha256={signature}",
                        },
                    )
                    item.response_status = response.status_code
                    if 200 <= response.status_code < 300:
                        item.status = WebhookDeliveryStatus.DELIVERED.value
                        item.delivered_at = now
                        item.last_error = None
                        delivered += 1
                    else:
                        raise httpx.HTTPStatusError(
                            f"HTTP {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                except httpx.HTTPError as exc:
                    item.last_error = str(exc)[:1000]
                    if item.attempts >= settings.WEBHOOK_MAX_ATTEMPTS:
                        item.status = WebhookDeliveryStatus.FAILED.value
                        failed += 1
                    else:
                        item.status = WebhookDeliveryStatus.RETRYING.value
                        item.next_attempt_at = now + timedelta(
                            seconds=settings.WEBHOOK_RETRY_BASE_SECONDS
                            * (2 ** (item.attempts - 1))
                        )
                        retrying += 1
                await self.repository.save_delivery(item)
        return {
            "processed": len(deliveries),
            "delivered": delivered,
            "retrying": retrying,
            "failed": failed,
        }

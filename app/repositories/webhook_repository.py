from datetime import datetime
from inspect import isawaitable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import Reservation
from app.models.resource import Resource
from app.models.webhook import WebhookDelivery, WebhookSubscription


class WebhookRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, subscription: WebhookSubscription) -> WebhookSubscription:
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def update(self, subscription: WebhookSubscription) -> WebhookSubscription:
        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def get_for_venue(
        self, subscription_id: int, venue_id: int
    ) -> WebhookSubscription | None:
        result = await self.db.execute(
            select(WebhookSubscription).where(
                WebhookSubscription.id == subscription_id,
                WebhookSubscription.venue_id == venue_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_venue(self, venue_id: int) -> list[WebhookSubscription]:
        result = await self.db.execute(
            select(WebhookSubscription)
            .where(WebhookSubscription.venue_id == venue_id)
            .order_by(WebhookSubscription.id)
        )
        return list(result.scalars().all())

    async def count_active(self, venue_id: int) -> int:
        result = await self.db.execute(
            select(WebhookSubscription.id).where(
                WebhookSubscription.venue_id == venue_id,
                WebhookSubscription.is_active.is_(True),
            )
        )
        return len(result.scalars().all())

    async def enqueue_for_event(self, event, commit: bool = True) -> int:
        result = await self.db.execute(
            select(WebhookSubscription)
            .join(Resource, Resource.venue_id == WebhookSubscription.venue_id)
            .join(Reservation, Reservation.resource_id == Resource.id)
            .where(
                Reservation.id == event.reservation_id,
                WebhookSubscription.is_active.is_(True),
            )
        )
        scalars = result.scalars()
        if isawaitable(scalars):
            scalars = await scalars
        items = scalars.all()
        if isawaitable(items):
            items = await items
        subscriptions = [item for item in items if event.event_type in item.event_types]
        if not subscriptions:
            if commit:
                await self.db.commit()
            return 0
        now = event.occurred_at
        payload = {
            "id": event.id,
            "type": f"reservation.{event.event_type}",
            "occurred_at": event.occurred_at.isoformat(),
            "data": {
                "reservation_id": event.reservation_id,
                "previous_status": event.previous_status,
                "status": event.new_status,
                "actor_role": event.actor_role,
                "details": event.details,
            },
        }
        for subscription in subscriptions:
            self.db.add(
                WebhookDelivery(
                    subscription_id=subscription.id,
                    event_id=event.id,
                    event_type=event.event_type,
                    payload=payload,
                    next_attempt_at=now,
                )
            )
        if commit:
            await self.db.commit()
        return len(subscriptions)

    async def list_deliveries(
        self, venue_id: int, limit: int = 100
    ) -> list[WebhookDelivery]:
        result = await self.db.execute(
            select(WebhookDelivery)
            .join(WebhookSubscription)
            .where(WebhookSubscription.venue_id == venue_id)
            .order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_delivery_for_venue(
        self, delivery_id: int, venue_id: int
    ) -> WebhookDelivery | None:
        result = await self.db.execute(
            select(WebhookDelivery)
            .join(WebhookSubscription)
            .where(
                WebhookDelivery.id == delivery_id,
                WebhookSubscription.venue_id == venue_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_due_deliveries(
        self, now: datetime, limit: int
    ) -> list[WebhookDelivery]:
        result = await self.db.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.status.in_(["pending", "retrying"]),
                WebhookDelivery.next_attempt_at <= now,
            )
            .order_by(WebhookDelivery.next_attempt_at, WebhookDelivery.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def get_subscription(
        self, subscription_id: int
    ) -> WebhookSubscription | None:
        return await self.db.get(WebhookSubscription, subscription_id)

    async def save_delivery(self, delivery: WebhookDelivery) -> None:
        await self.db.commit()

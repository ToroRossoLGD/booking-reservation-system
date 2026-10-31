from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.models.notification import Notification
from app.models.rental_inquiry import RentalInquiry
from app.models.sale_inquiry import SaleInquiry
from app.models.viewing_reminder import (
    ViewingReminderDelivery,
    ViewingReminderPreference,
)
from app.repositories.stay_repository import StayRepository


async def viewing_preference(db, user_id):
    row = await db.get(ViewingReminderPreference, user_id)
    return row.enabled if row else True


async def set_viewing_preference(db, user_id, enabled):
    await StayRepository(db).lock_user(user_id)
    row = await db.get(ViewingReminderPreference, user_id)
    if row is None:
        db.add(ViewingReminderPreference(user_id=user_id, enabled=enabled))
    else:
        row.enabled = enabled
    await db.commit()
    return {"enabled": enabled}


async def remind_viewing(db, inquiry_id, sale, now):
    model = SaleInquiry if sale else RentalInquiry
    inquiry = await db.scalar(
        select(model)
        .where(model.id == inquiry_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        inquiry is None
        or inquiry.status != "viewing_confirmed"
        or inquiry.viewing_at is None
    ):
        return 0
    viewing = inquiry.viewing_at
    viewing = (
        viewing.replace(tzinfo=UTC)
        if viewing.tzinfo is None
        else viewing.astimezone(UTC)
    )
    if not now < viewing <= now + timedelta(hours=24):
        return 0
    kind = "sale_id" if sale else "rental_id"
    path = "sales" if sale else "rentals"
    sent = 0
    # Inquiry participants stay authoritative, matching the existing conversation.
    for user_id, destination in {
        inquiry.owner_id: f"/owner/{path}",
        inquiry.user_id: f"/{path}",
    }.items():
        if not await viewing_preference(db, user_id):
            continue
        exists = await db.scalar(
            select(ViewingReminderDelivery.id).where(
                getattr(ViewingReminderDelivery, kind) == inquiry.id,
                ViewingReminderDelivery.user_id == user_id,
                ViewingReminderDelivery.viewing_at == viewing,
            )
        )
        if exists is not None:
            continue
        db.add(
            Notification(
                user_id=user_id,
                title="Podsetnik za potvrđeno razgledanje",
                message=(
                    f"{inquiry.title}: razgledanje {viewing:%d.%m.%Y. u %H:%M} UTC. "
                    "Otvori upit za prikaz u lokalnom vremenu "
                    "i proveri aktuelni dogovor pre polaska."
                ),
                action_path=destination,
            )
        )
        db.add(
            ViewingReminderDelivery(
                **{kind: inquiry.id}, user_id=user_id, viewing_at=viewing
            )
        )
        sent += 1
    await db.commit()
    return sent


async def run_viewing_reminders(sessions, now=None):
    if settings.DEMO_MODE or not settings.VIEWING_REMINDERS_ENABLED:
        return {"sent": 0}
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("Reminder time must include a timezone")
    now = now.astimezone(UTC)
    sent = 0
    for sale, model in ((False, RentalInquiry), (True, SaleInquiry)):
        cursor = 0
        while True:
            async with sessions() as db:
                ids = list(
                    (
                        await db.scalars(
                            select(model.id)
                            .where(
                                model.id > cursor,
                                model.status == "viewing_confirmed",
                                model.viewing_at > now,
                                model.viewing_at <= now + timedelta(hours=24),
                            )
                            .order_by(model.id)
                            .limit(100)
                        )
                    ).all()
                )
            if not ids:
                break
            for inquiry_id in ids:
                async with sessions() as db:
                    sent += await remind_viewing(db, inquiry_id, sale, now)
            cursor = ids[-1]
    return {"sent": sent}

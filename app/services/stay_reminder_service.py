from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import or_, select

from app.core.config import settings
from app.models.notification import Notification
from app.models.stay import Stay
from app.models.stay_reminder import StayReminderDelivery, StayReminderPreference
from app.repositories.stay_repository import StayRepository


async def reminder_preference(db, user_id):
    row = await db.get(StayReminderPreference, user_id)
    return row.enabled if row else True


async def set_reminder_preference(db, user_id, enabled):
    await StayRepository(db).lock_user(user_id)
    row = await db.get(StayReminderPreference, user_id)
    if row is None:
        row = StayReminderPreference(user_id=user_id, enabled=enabled)
        db.add(row)
    else:
        row.enabled = enabled
    await db.commit()
    return {"enabled": enabled}


async def remind_stay(db, stay_id, now):
    repo = StayRepository(db)
    initial = await db.get(Stay, stay_id)
    if initial is None:
        return 0
    await repo.listing(initial.property_id, lock=True)
    venue = await repo.lock_venue(initial.venue_id)
    stay = await db.scalar(
        select(Stay)
        .where(Stay.id == stay_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if not venue or stay.status != "confirmed":
        return 0
    try:
        local = now.astimezone(ZoneInfo(stay.timezone))
    except ZoneInfoNotFoundError:
        return 0
    if local.hour < 9:
        return 0
    tomorrow = local.date() + timedelta(days=1)
    sent = 0
    for kind, event_date, event_time in (
        ("arrival", stay.check_in, stay.check_in_time),
        ("departure", stay.check_out, stay.check_out_time),
    ):
        if event_date != tomorrow:
            continue
        # One personal reminder even if the guest also owns the venue.
        recipients = {venue.owner_id: "/owner/stays", stay.user_id: "/stays"}
        for user_id, path in recipients.items():
            if not await reminder_preference(db, user_id):
                continue
            previous = await db.scalar(
                select(StayReminderDelivery.id).where(
                    StayReminderDelivery.stay_id == stay.id,
                    StayReminderDelivery.user_id == user_id,
                    StayReminderDelivery.kind == kind,
                    StayReminderDelivery.event_date == event_date,
                )
            )
            if previous is not None:
                continue
            label = "Dolazak" if kind == "arrival" else "Odlazak"
            time_text = (
                f" u {event_time}" if event_time else " (satnicu proveri sa domaćinom)"
            )
            db.add(
                Notification(
                    user_id=user_id,
                    title=f"Sutra: {label.lower()} u rezervaciji #{stay.id}",
                    message=(
                        f"{stay.title}: {label} {event_date:%d.%m.%Y.}{time_text}. "
                        f"Vremenska zona: {stay.timezone}. "
                        "Proveri aktuelne detalje rezervacije pre puta."
                    ),
                    action_path=path,
                )
            )
            db.add(
                StayReminderDelivery(
                    stay_id=stay.id, user_id=user_id, kind=kind, event_date=event_date
                )
            )
            sent += 1
    await db.commit()
    return sent


async def run_stay_reminders(sessions, now=None):
    if settings.DEMO_MODE or not settings.STAY_REMINDERS_ENABLED:
        return {"sent": 0}
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("Reminder time must include a timezone")
    now = now.astimezone(UTC)
    # All possible local tomorrows, including UTC-12 and UTC+14.
    first, last = now.date(), now.date() + timedelta(days=2)
    cursor, sent = 0, 0
    while True:
        async with sessions() as db:
            ids = list(
                (
                    await db.scalars(
                        select(Stay.id)
                        .where(
                            Stay.id > cursor,
                            Stay.status == "confirmed",
                            or_(
                                Stay.check_in.between(first, last),
                                Stay.check_out.between(first, last),
                            ),
                        )
                        .order_by(Stay.id)
                        .limit(100)
                    )
                ).all()
            )
        if not ids:
            break
        for stay_id in ids:
            async with sessions() as db:
                sent += await remind_stay(db, stay_id, now)
        cursor = ids[-1]
    return {"sent": sent}

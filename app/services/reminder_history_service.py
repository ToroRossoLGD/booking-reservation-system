from datetime import UTC

from sqlalchemy import select

from app.models.stay_reminder import StayReminderDelivery
from app.models.viewing_reminder import ViewingReminderDelivery


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def reminder_history(db, user_id, viewing, offset):
    model = ViewingReminderDelivery if viewing else StayReminderDelivery
    rows = list(
        (
            await db.scalars(
                select(model)
                .where(model.user_id == user_id)
                .order_by(model.created_at.desc(), model.id.desc())
                .offset(offset)
                .limit(21)
            )
        ).all()
    )
    items = []
    for row in rows[:20]:
        if viewing:
            kind = "rental_viewing" if row.rental_id is not None else "sale_viewing"
            reference_id = row.rental_id if row.rental_id is not None else row.sale_id
            scheduled_for = utc(row.viewing_at).isoformat()
        else:
            kind, reference_id = row.kind, row.stay_id
            scheduled_for = row.event_date.isoformat()
        items.append(
            {
                "id": row.id,
                "kind": kind,
                "reference_id": reference_id,
                "scheduled_for": scheduled_for,
                "created_at": utc(row.created_at),
            }
        )
    return {"items": items, "offset": offset, "has_next": len(rows) > 20}

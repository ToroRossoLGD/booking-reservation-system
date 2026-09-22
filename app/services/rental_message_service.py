from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select, update

from app.models.rental_inquiry import RentalInquiry
from app.models.rental_message import RentalMessage
from app.schemas.rental_message import RentalMessageRead


def append_rental_message(
    db, inquiry, sender_id, body, kind="message", viewing_at=None, request_id=None
):
    message = RentalMessage(
        inquiry_id=inquiry.id,
        sender_id=sender_id,
        body=body,
        kind=kind,
        viewing_at=viewing_at,
        request_id=request_id,
    )
    db.add(message)
    return message


class RentalMessageService:
    def __init__(self, db):
        self.db = db

    async def participant_inquiry(self, inquiry_id, user, lock=False):
        query = select(RentalInquiry).where(
            RentalInquiry.id == inquiry_id,
            (RentalInquiry.user_id == user.id) | (RentalInquiry.owner_id == user.id),
        )
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        inquiry = await self.db.scalar(query)
        if inquiry is None:
            raise HTTPException(404, "Inquiry not found")
        return inquiry

    @staticmethod
    def read(message, inquiry):
        return RentalMessageRead(
            id=message.id,
            sender="owner" if message.sender_id == inquiry.owner_id else "tenant",
            kind=message.kind,
            body=message.body,
            viewing_at=message.viewing_at,
            created_at=message.created_at,
            read_at=message.read_at,
        )

    async def list(self, inquiry_id, user, before_id=None, limit=50):
        inquiry = await self.participant_inquiry(inquiry_id, user)
        query = select(RentalMessage).where(RentalMessage.inquiry_id == inquiry_id)
        if before_id is not None:
            query = query.where(RentalMessage.id < before_id)
        rows = list(
            await self.db.scalars(
                query.order_by(RentalMessage.id.desc()).limit(limit + 1)
            )
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [self.read(message, inquiry) for message in reversed(rows)],
            "has_more": has_more,
            "next_before_id": rows[-1].id if has_more else None,
            "unread_count": await self.unread_count(inquiry_id, user),
        }

    async def unread_count(self, inquiry_id, user):
        return await self.db.scalar(
            select(func.count())
            .select_from(RentalMessage)
            .where(
                RentalMessage.inquiry_id == inquiry_id,
                RentalMessage.sender_id != user.id,
                RentalMessage.read_at.is_(None),
            )
        )

    async def send(self, inquiry_id, data, user):
        inquiry = await self.participant_inquiry(inquiry_id, user, lock=True)
        previous = await self.db.scalar(
            select(RentalMessage).where(
                RentalMessage.inquiry_id == inquiry_id,
                RentalMessage.sender_id == user.id,
                RentalMessage.request_id == str(data.request_id),
            )
        )
        if previous:
            if previous.body != data.body:
                raise HTTPException(409, "This request identifier was already used")
            return self.read(previous, inquiry)
        if inquiry.status in {"closed", "withdrawn"}:
            raise HTTPException(409, "This inquiry is no longer active")
        message = append_rental_message(
            self.db, inquiry, user.id, data.body, request_id=str(data.request_id)
        )
        # A chat message does not alter the version of a viewing proposal.
        await self.db.commit()
        await self.db.refresh(message)
        return self.read(message, inquiry)

    async def mark_read(self, inquiry_id, data, user):
        await self.participant_inquiry(inquiry_id, user, lock=True)
        await self.db.execute(
            update(RentalMessage)
            .where(
                RentalMessage.inquiry_id == inquiry_id,
                RentalMessage.id.in_(data.message_ids),
                RentalMessage.sender_id != user.id,
                RentalMessage.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        count = await self.unread_count(inquiry_id, user)
        await self.db.commit()
        return {"unread_count": count}

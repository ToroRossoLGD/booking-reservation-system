from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.models.notification import Notification
from app.models.rental_inquiry import RentalInquiry
from app.models.rental_message import RentalMessage
from app.schemas.rental_inquiry import RentalInquiryUpdate
from tests import test_rental_inquiries as rentals

service = rentals.service


@pytest.mark.asyncio
async def test_milestones_notify_other_participant_without_duplicates(
    service,
):
    data = rentals.inquiry_data()
    inquiry = await service.create(1, data, rentals.TENANT)
    db = service.db
    note = await db.scalar(select(Notification))
    assert note.user_id == rentals.OWNER.id
    assert note.action_path == "/owner/rentals"
    assert note.title == "Novi upit za dugoročni najam"
    assert f"#{inquiry.id}" in note.message
    await service.create(1, data, rentals.TENANT)
    assert await db.scalar(select(func.count(Notification.id))) == 1
    await db.execute(delete(Notification))
    await db.commit()
    await service.create(1, data, rentals.TENANT)
    assert await db.scalar(select(func.count(Notification.id))) == 0

    viewing = datetime.now(timezone.utc) + timedelta(days=2)
    actions = [
        ("propose", rentals.OWNER, rentals.TENANT, "/rentals"),
        ("decline", rentals.TENANT, rentals.OWNER, "/owner/rentals"),
        ("propose", rentals.OWNER, rentals.TENANT, "/rentals"),
        ("confirm", rentals.TENANT, rentals.OWNER, "/owner/rentals"),
        ("close", rentals.OWNER, rentals.TENANT, "/rentals"),
    ]
    for count, (action, actor, recipient, path) in enumerate(actions, 1):
        update = RentalInquiryUpdate(
            version=inquiry.version,
            action=action,
            **(
                {"owner_reply": "Meet at the entrance.", "viewing_at": viewing}
                if action == "propose"
                else {}
            ),
        )
        await service.update(inquiry.id, update, actor)
        note = await db.scalar(select(Notification).order_by(Notification.id.desc()))
        assert note.user_id == recipient.id and note.action_path == path
        assert await db.scalar(select(func.count(Notification.id))) == count
        if action in {"propose", "confirm"}:
            assert "UTC" in note.message
        with pytest.raises(HTTPException) as error:
            await service.update(inquiry.id, update, actor)
        assert error.value.status_code == 409
        assert await db.scalar(select(func.count(Notification.id))) == count


@pytest.mark.asyncio
async def test_reply_is_not_a_milestone_and_withdrawal_notifies_owner(service):
    inquiry = await service.create(1, rentals.inquiry_data(), rentals.TENANT)
    await service.update(
        inquiry.id,
        RentalInquiryUpdate(
            version=1, action="reply", owner_reply="Thanks for your interest."
        ),
        rentals.OWNER,
    )
    assert await service.db.scalar(select(func.count(Notification.id))) == 1
    with pytest.raises(HTTPException):
        await service.update(
            inquiry.id, RentalInquiryUpdate(version=2, action="withdraw"), rentals.OTHER
        )
    assert await service.db.scalar(select(func.count(Notification.id))) == 1
    await service.update(
        inquiry.id, RentalInquiryUpdate(version=2, action="withdraw"), rentals.TENANT
    )
    note = await service.db.scalar(
        select(Notification).order_by(Notification.id.desc())
    )
    assert note.user_id == rentals.OWNER.id and note.title == "Zakupac je povukao upit"


@pytest.mark.asyncio
@pytest.mark.parametrize("existing", [False, True])
async def test_notification_failure_rolls_back_inquiry_and_conversation(
    service, existing
):
    db = service.db
    inquiry = (
        await service.create(1, rentals.inquiry_data(), rentals.TENANT)
        if existing
        else None
    )
    inquiry_id = inquiry.id if inquiry else None
    original_add = db.add

    def fail_notification(item):
        if isinstance(item, Notification):
            raise RuntimeError("Notification write failed")
        original_add(item)

    db.add = fail_notification
    db.commit.reset_mock()
    with pytest.raises(RuntimeError):
        if existing:
            await service.update(
                inquiry_id,
                RentalInquiryUpdate(version=1, action="withdraw"),
                rentals.TENANT,
            )
        else:
            await service.create(1, rentals.inquiry_data(), rentals.TENANT)
    db.commit.assert_not_awaited()
    await db.rollback()
    for model in [Notification, RentalMessage, RentalInquiry]:
        assert await db.scalar(select(func.count(model.id))) == int(existing)
    if existing:
        row = await db.scalar(
            select(RentalInquiry).where(RentalInquiry.id == inquiry_id)
        )
        assert row.status == "open" and row.version == 1

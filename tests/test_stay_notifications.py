import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import create_engine, delete, func, select, text

from app.models.notification import Notification
from app.models.stay import Stay
from app.schemas.notification import NotificationRead
from app.services.notification_service import NotificationService
from tests import test_stays

service = test_stays.service


@pytest.mark.asyncio
async def test_booking_and_cancellation_notify_only_participants_once(service):
    data = test_stays.booking()
    stay = await service.create(1, data, test_stays.GUEST)
    db = service.repository.db
    inbox = NotificationService(db)
    for user_id, path in [
        (test_stays.GUEST.id, "/stays"),
        (test_stays.OWNER.id, "/owner/stays"),
    ]:
        page = await inbox.get_my_notifications(user_id, 20, 0)
        assert page["total"] == 1
        note = NotificationRead.model_validate(page["items"][0])
        assert note.action_path == path and not note.is_read
        assert f"#{stay.id}" in note.message
        assert stay.title in note.message and "195.00 EUR" in note.message
        assert "03.10.2026." in note.message and "Europe/Belgrade" in note.message
        assert await inbox.get_unread_count(user_id) == 1
    assert (await inbox.get_my_notifications(test_stays.OTHER.id, 20, 0))["total"] == 0
    guest_note = (await inbox.get_my_notifications(test_stays.GUEST.id, 20, 0))[
        "items"
    ][0]
    for actor in [test_stays.OTHER, test_stays.OWNER]:
        with pytest.raises(HTTPException) as error:
            await inbox.mark_notification_as_read(guest_note.id, actor.id)
        assert error.value.status_code == 404
    await service.create(1, data, test_stays.GUEST)
    assert await db.scalar(select(func.count(Notification.id))) == 2
    # Dismissing an event must not make a retry recreate it.
    await db.execute(delete(Notification).where(Notification.id == guest_note.id))
    await db.commit()
    await service.create(1, data, test_stays.GUEST)
    assert await db.scalar(select(func.count(Notification.id))) == 1
    await service.cancel(stay.id, test_stays.GUEST)
    await service.cancel(stay.id, test_stays.GUEST)
    assert await db.scalar(select(func.count(Notification.id))) == 3
    guest_page = await inbox.get_my_notifications(test_stays.GUEST.id, 20, 0)
    assert guest_page["items"][0].title == "Boravak je otkazan"
    assert guest_page["items"][0].action_path == "/stays"


@pytest.mark.asyncio
async def test_rejected_booking_and_unauthorized_cancel_do_not_notify(service):
    db = service.repository.db
    with pytest.raises(HTTPException):
        await service.create(
            1, test_stays.booking(expected_total_cents=1), test_stays.GUEST
        )
    assert await db.scalar(select(func.count(Notification.id))) == 0
    stay = await service.create(1, test_stays.booking(), test_stays.GUEST)
    with pytest.raises(HTTPException):
        await service.create(2, test_stays.booking(), test_stays.OTHER)
    with pytest.raises(HTTPException):
        await service.cancel(stay.id, test_stays.OTHER)
    assert await db.scalar(select(func.count(Notification.id))) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_notification_failure_rolls_back_the_entire_transition(service, cancel):
    db = service.repository.db
    stay = (
        await service.create(1, test_stays.booking(), test_stays.GUEST)
        if cancel
        else None
    )
    stay_id = stay.id if stay else None
    original_add = db.add

    def fail_second_recipient(item):
        if isinstance(item, Notification) and item.user_id == test_stays.OWNER.id:
            raise RuntimeError("Unable to write owner notification")
        original_add(item)

    db.add = fail_second_recipient
    db.commit.reset_mock()
    with pytest.raises(RuntimeError):
        if cancel:
            await service.cancel(stay_id, test_stays.GUEST)
        else:
            await service.create(1, test_stays.booking(), test_stays.GUEST)
    db.commit.assert_not_awaited()
    await db.rollback()
    assert await db.scalar(select(func.count(Notification.id))) == (2 if cancel else 0)
    assert await db.scalar(select(func.count(Stay.id))) == (1 if cancel else 0)
    if cancel:
        assert (
            await db.scalar(select(Stay.status).where(Stay.id == stay_id))
            == "confirmed"
        )


def test_notification_navigation_migration_preserves_old_messages():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/eb613f768029_add_notification_action_path.py"
    )
    spec = importlib.util.spec_from_file_location("notification_navigation", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE notifications (id INTEGER PRIMARY KEY, message TEXT)")
        )
        connection.execute(
            text("INSERT INTO notifications VALUES (1, 'Existing notification')")
        )
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert tuple(connection.execute(text("SELECT * FROM notifications")).one()) == (
            1,
            "Existing notification",
            None,
        )
        migration.downgrade()
        assert tuple(connection.execute(text("SELECT * FROM notifications")).one()) == (
            1,
            "Existing notification",
        )
    engine.dispose()

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, delete, inspect, text

from app.api.routers.notifications import router
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.stay_reminder import StayReminderDelivery
from app.models.viewing_reminder import ViewingReminderDelivery
from tests import test_stays, test_viewing_reminders

service = test_stays.service
db = test_viewing_reminders.db
NOW = datetime(2026, 11, 1, 10, tzinfo=UTC)


@pytest.mark.asyncio
@pytest.mark.parametrize("viewing", [False, True])
async def test_history_auth_recipient_pagination_and_deleted_inbox(
    db, service, viewing
):
    session = db.scalar.side_effect.__self__
    StayReminderDelivery.__table__.create(session.get_bind())
    stay = await service.create(1, test_stays.booking(), test_stays.GUEST)
    rental = await test_viewing_reminders.seed_inquiry(db)
    sale = await test_viewing_reminders.seed_inquiry(db, True)
    for index in range(25):
        for user_id in (2, 3):
            if viewing:
                row = ViewingReminderDelivery(
                    user_id=user_id,
                    rental_id=rental.id if index % 2 else None,
                    sale_id=sale.id if not index % 2 else None,
                    viewing_at=NOW + timedelta(days=index),
                    created_at=NOW,
                )
            else:
                row = StayReminderDelivery(
                    user_id=user_id,
                    stay_id=stay.id,
                    kind="arrival" if index % 2 else "departure",
                    event_date=NOW.date() + timedelta(days=index),
                    created_at=NOW,
                )
            db.add(row)
    await db.commit()
    await db.execute(delete(Notification))
    await db.commit()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    path = f"/notifications/{'viewing' if viewing else 'stay'}-reminders/history"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get(path)).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: test_stays.GUEST
        response = await client.get(path)
        assert response.headers["cache-control"] == "private, no-store"
        first = response.json()
        assert len(first["items"]) == 20 and first["has_next"]
        assert {item["kind"] for item in first["items"]} == (
            {"rental_viewing", "sale_viewing"} if viewing else {"arrival", "departure"}
        )
        assert all(item["id"] % 2 == 1 for item in first["items"])
        assert first["items"][0]["id"] == 49
        assert set(first["items"][0]) == {
            "id",
            "kind",
            "reference_id",
            "scheduled_for",
            "created_at",
        }
        assert first["items"][0]["created_at"].endswith("Z")
        second = (await client.get(path, params={"offset": 20})).json()
        assert len(second["items"]) == 5 and not second["has_next"]
        assert not {r["id"] for r in first["items"]} & {
            r["id"] for r in second["items"]
        }
        assert (await client.get(path, params={"offset": -1})).status_code == 422
        app.dependency_overrides[get_current_user] = lambda: test_stays.OWNER
        assert (await client.get(path)).json()["items"] == []


def test_history_index_migration_roundtrip():
    spec = importlib.util.spec_from_file_location(
        "history_migration", Path("alembic/versions/b49d60ef5378_reminder_history.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for kind in ("stay", "viewing"):
            connection.execute(
                text(
                    f"CREATE TABLE {kind}_reminder_deliveries "
                    "(id INTEGER, user_id INTEGER, created_at DATETIME)"
                )
            )
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        for kind in ("stay", "viewing"):
            assert inspect(connection).get_indexes(f"{kind}_reminder_deliveries")[0][
                "column_names"
            ] == ["user_id", "created_at", "id"]
        module.downgrade()
        assert not inspect(connection).get_indexes("stay_reminder_deliveries")
    engine.dispose()

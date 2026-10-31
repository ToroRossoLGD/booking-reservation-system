import asyncio
import importlib.util
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.routers.notifications import router
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.notification import Notification
from app.models.property_email_digest import (
    PropertyEmailDigest,
    PropertyEmailDigestItem,
)
from app.models.user import User
from app.services import property_email_digest_service as module
from app.services.email_service import EmailDeliveryError, EmailService
from tests import test_stays
from tests.test_stay_reminders import sessions_for

service = test_stays.service


@pytest.fixture
def setup(service, monkeypatch):
    db = service.repository.db
    session = db.scalar.side_effect.__self__
    for table in (PropertyEmailDigest.__table__, PropertyEmailDigestItem.__table__):
        table.create(session.get_bind())
    session.get(User, 2).email_verified_at = datetime.now(UTC)
    session.commit()
    monkeypatch.setattr(settings, "PROPERTY_EMAIL_DIGEST_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_MODE", "plain")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    sender = Mock()
    monkeypatch.setattr(EmailService, "send_email", sender)
    return db, sender


async def notice(db, user_id=2, path="/stays", id=None):
    row = Notification(
        user_id=user_id,
        title="Private title",
        message="Private conversation",
        action_path=path,
    )
    if id is not None:
        row.id = id
    db.add(row)
    await db.commit()
    return row


async def due(db):
    row = await db.get(PropertyEmailDigest, 2)
    row.next_run_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()


@pytest.mark.asyncio
async def test_opt_in_excludes_backlog_and_sends_private_count_once(setup):
    db, sender = setup
    user = await db.get(User, 2)
    assert not (await module.status(db, user))["enabled"]
    await notice(db)
    await module.configure(db, user, True)
    await notice(db, path="/rentals")
    await notice(db, path="/moderation")
    await notice(db, user_id=3)
    await due(db)
    assert await module.run_email_digests(sessions_for(db)) == {"accepted": 1}
    sender.assert_called_once()
    recipient, subject, body = sender.call_args.args
    assert recipient == user.email
    assert "1 novih" in body and "/account/notifications" in body
    assert "Private" not in body and "Private" not in subject
    assert (await module.status(db, user))["last_accepted_at"] is not None
    await due(db)
    assert await module.run_email_digests(sessions_for(db)) == {}
    assert sender.call_count == 1


@pytest.mark.asyncio
async def test_late_commits_and_bounded_batches_are_not_skipped(setup):
    db, sender = setup
    await module.configure(db, await db.get(User, 2), True)
    await notice(db, id=100)
    await due(db)
    await module.run_email_digests(sessions_for(db))
    # A lower sequence ID becoming visible after a higher ID was delivered.
    await notice(db, id=50)
    for _ in range(22):
        await notice(db)
    await due(db)
    await module.run_email_digests(sessions_for(db))
    assert "20 novih" in sender.call_args.args[2]
    await due(db)
    await module.run_email_digests(sessions_for(db))
    assert "3 novih" in sender.call_args.args[2]
    assert len(list((await db.scalars(select(PropertyEmailDigestItem))).all())) == 24


@pytest.mark.asyncio
async def test_failed_delivery_retries_then_disables_without_marking_accepted(setup):
    db, sender = setup
    user = await db.get(User, 2)
    await module.configure(db, user, True)
    await notice(db)
    sender.side_effect = EmailDeliveryError("sanitized")
    for _ in range(3):
        await due(db)
        assert await module.run_email_digests(sessions_for(db)) == {"failed": 1}
    status = await module.status(db, user)
    assert not status["enabled"] and status["last_accepted_at"] is None
    assert not list((await db.scalars(select(PropertyEmailDigestItem))).all())


@pytest.mark.asyncio
async def test_expired_claim_replaced_and_post_smtp_rollback_is_not_success(setup):
    db, sender = setup
    await module.configure(db, await db.get(User, 2), True)
    await notice(db)
    await due(db)
    sessions = sessions_for(db)
    old = await module.claim(sessions)
    row = await db.get(PropertyEmailDigest, 2)
    row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    await due(db)
    job = await module.claim(sessions)
    assert old["token"] != job["token"]
    assert await module.send_and_finish(sessions, old) == "discarded"
    sender.assert_not_called()
    commit = db.commit
    db.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    with pytest.raises(RuntimeError):
        await module.send_and_finish(sessions, job)
    await db.rollback()
    db.commit = commit
    assert not list((await db.scalars(select(PropertyEmailDigestItem))).all())
    assert (await module.status(db, await db.get(User, 2)))["last_accepted_at"] is None
    assert await module.send_and_finish(sessions, job) == "accepted"
    # SMTP acceptance followed by failed DB commit can duplicate a count summary.
    assert sender.call_count == 2


@pytest.mark.asyncio
async def test_pause_invalidates_claim_and_unverified_or_disabled_never_sends(
    setup, monkeypatch
):
    db, sender = setup
    user = await db.get(User, 2)
    await module.configure(db, user, True)
    await notice(db)
    await due(db)
    sessions = sessions_for(db)
    job = await module.claim(sessions)
    assert await module.claim(sessions) is None
    await module.configure(db, user, False)
    assert await module.send_and_finish(sessions, job) == "discarded"
    await module.configure(db, user, True)
    await notice(db)
    await due(db)
    monkeypatch.setattr(settings, "SMTP_MODE", "disabled")
    assert await module.run_email_digests(sessions) == {}
    monkeypatch.setattr(settings, "SMTP_MODE", "plain")
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    assert await module.run_email_digests(sessions) == {}
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    user.email_verified_at = None
    await db.commit()
    assert await module.run_email_digests(sessions) == {}
    assert (await module.status(db, user))["last_status"] == "unverified"
    with pytest.raises(HTTPException):
        await module.configure(db, user, True)
    sender.assert_not_called()


@pytest.mark.asyncio
async def test_api_auth_strict_consent_and_no_recipient_override(setup):
    db, _ = setup
    user = await db.get(User, 2)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        path = "/notifications/email-digest"
        assert (await client.get(path)).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user
        assert (await client.put(path, json={"enabled": "true"})).status_code == 422
        assert (
            await client.put(path, json={"enabled": True, "email": "other@example.com"})
        ).status_code == 422
        result = await client.put(path, json={"enabled": True})
        assert result.status_code == 200 and result.json()["enabled"]
        assert result.headers["cache-control"] == "private, no-store"
        assert user.email not in result.text
        app.dependency_overrides[get_current_user] = lambda: test_stays.OTHER
        # Use the actual account object, matching the production dependency.
        other = await db.get(User, 3)
        app.dependency_overrides[get_current_user] = lambda: other
        assert not (await client.get(path)).json()["enabled"]


def test_migration_and_task_registration():
    from app.tasks.celery_app import celery_app

    spec = importlib.util.spec_from_file_location(
        "digest_migration",
        Path("alembic/versions/c50e71fa6489_property_email_digest.py"),
    )
    module_ = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module_)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        module_.op = Operations(MigrationContext.configure(connection))
        module_.upgrade()
        assert "property_email_digest_items" in inspect(connection).get_table_names()
        module_.downgrade()
        assert not inspect(connection).get_table_names()
    engine.dispose()
    assert (
        celery_app.conf.beat_schedule["send-property-email-digests"]["task"]
        == "send_property_email_digests"
    )


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("STAY_TEST_POSTGRES") != "1", reason="PostgreSQL opt-in")
async def test_postgres_exclusive_claim_and_delivery(monkeypatch):
    monkeypatch.setattr(settings, "PROPERTY_EMAIL_DIGEST_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_MODE", "plain")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    sender = Mock()
    monkeypatch.setattr(EmailService, "send_email", sender)
    schema = "email_digest_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(
                    sync,
                    tables=[
                        User.__table__,
                        Notification.__table__,
                        PropertyEmailDigest.__table__,
                        PropertyEmailDigestItem.__table__,
                    ],
                )
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            user = User(
                id=2,
                email="test@example.com",
                hashed_password="test",
                email_verified_at=datetime.now(UTC),
            )
            db.add(user)
            await db.commit()
            await module.configure(db, user, True)
            await notice(db)
            await due(db)
        results = await asyncio.gather(
            module.run_email_digests(sessions), module.run_email_digests(sessions)
        )
        assert sum(result.get("accepted", 0) for result in results) == 1
        sender.assert_called_once()
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()

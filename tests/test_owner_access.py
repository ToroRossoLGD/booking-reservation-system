import asyncio
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.db.base import Base
from app.models.api_key import APIKey
from app.models.notification import Notification
from app.models.owner_access_request import OwnerAccessRequest
from app.models.user import User
from app.schemas.owner_access import OwnerAccessCreate, OwnerAccessDecision
from app.services.owner_access_service import OwnerAccessService

CUSTOMER = SimpleNamespace(id=1)
OTHER = SimpleNamespace(id=2)
ADMIN = SimpleNamespace(id=3)


def body(**changes):
    return OwnerAccessCreate(
        **(
            dict(request_id=uuid4(), details="I manage two apartments for short stays.")
            | changes
        )
    )


def decision(action="approved", note="Account and authority reviewed."):
    return OwnerAccessDecision(action=action, note=note)


def seed(db):
    db.add_all(
        [
            User(
                id=i,
                email=f"u{i}@example.com",
                hashed_password="test",
                role="admin" if i == 3 else "customer",
                email_verified_at=datetime.now(UTC),
                token_version=0,
            )
            for i in (1, 2, 3)
        ]
    )
    db.flush()
    db.add(APIKey(user_id=1, name="old", key_prefix="prefix", key_hash="a" * 64))
    db.commit()


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            APIKey.__table__,
            Notification.__table__,
            OwnerAccessRequest.__table__,
        ],
    )
    with Session(engine, expire_on_commit=False) as session:
        seed(session)
        db = MagicMock()
        db.add = session.add
        for name in ("scalar", "scalars", "execute", "flush", "commit", "rollback"):
            setattr(db, name, AsyncMock(side_effect=getattr(session, name)))
        yield OwnerAccessService(db)
    engine.dispose()


@pytest.mark.asyncio
async def test_submission_privacy_retry_and_pending_conflict(service):
    data = body()
    first = await service.create(data, CUSTOMER)
    assert (await service.create(data, CUSTOMER)).id == first.id
    assert len((await service.page(CUSTOMER)).items) == 1
    assert (await service.page(OTHER)).items == []
    for command, status in (
        (body(), 409),
        (
            body(
                request_id=data.request_id,
                details="Another description of managed property.",
            ),
            409,
        ),
    ):
        with pytest.raises(HTTPException) as error:
            await service.create(command, CUSTOMER)
        assert error.value.status_code == status
    with pytest.raises(HTTPException) as error:
        await service.page(CUSTOMER, admin=True)
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_approval_atomic_role_keys_notification_and_idempotent_decision(service):
    row = await service.create(body(), CUSTOMER)
    result = await service.decide(row.id, decision(), ADMIN)
    assert result.status == "approved" and result.decided_at
    user = await service.db.scalar(select(User).where(User.id == 1))
    assert user.role == "owner" and user.token_version == 1
    assert (await service.db.scalar(select(APIKey))).revoked_at
    assert (
        await service.db.scalar(select(Notification))
    ).action_path == "/owner-access"
    await service.decide(row.id, decision(), ADMIN)
    assert await service.db.scalar(select(func.count()).select_from(Notification)) == 1
    with pytest.raises(HTTPException) as error:
        await service.decide(row.id, decision("rejected"), ADMIN)
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_rejection_cooldown_resubmission_and_history(service):
    row = await service.create(body(), CUSTOMER)
    await service.decide(row.id, decision("rejected"), ADMIN)
    with pytest.raises(HTTPException) as error:
        await service.create(body(), CUSTOMER)
    assert error.value.status_code == 429
    record = await service.db.scalar(select(OwnerAccessRequest))
    record.created_at = datetime.now(UTC) - timedelta(days=2)
    await service.db.commit()
    await service.create(body(), CUSTOMER)
    history = await service.page(CUSTOMER)
    assert [item.status for item in history.items] == ["pending", "rejected"]
    user = await service.db.scalar(select(User).where(User.id == 1))
    assert user.role == "customer" and user.token_version == 0
    assert (await service.db.scalar(select(APIKey))).revoked_at is None


@pytest.mark.asyncio
async def test_verification_role_demo_and_admin_guards(service, monkeypatch):
    user = await service.db.scalar(select(User).where(User.id == 1))
    user.email_verified_at = None
    await service.db.commit()
    for actor in (CUSTOMER, ADMIN):
        with pytest.raises(HTTPException) as error:
            await service.create(body(), actor)
        assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        await service.decide(1, decision(), OTHER)
    assert error.value.status_code == 403
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    with pytest.raises(HTTPException):
        await service.create(body(), OTHER)


@pytest.mark.asyncio
async def test_changed_account_blocks_approval_and_failure_rolls_back(service):
    row = await service.create(body(), CUSTOMER)
    user = await service.db.scalar(select(User).where(User.id == 1))
    user.email = "changed@example.com"
    await service.db.commit()
    with pytest.raises(HTTPException) as error:
        await service.decide(row.id, decision(), ADMIN)
    assert error.value.status_code == 409
    user = await service.db.scalar(select(User).where(User.id == 1))
    user.email = "u1@example.com"
    await service.db.commit()
    original = service.db.commit.side_effect
    service.db.commit.side_effect = RuntimeError("commit failed")
    with pytest.raises(RuntimeError):
        await service.decide(row.id, decision(), ADMIN)
    service.db.commit.side_effect = original
    user = await service.db.scalar(select(User).where(User.id == 1))
    assert user.role == "customer" and user.token_version == 0
    assert (await service.db.scalar(select(APIKey))).revoked_at is None
    assert (await service.db.scalar(select(OwnerAccessRequest))).status == "pending"
    assert await service.db.scalar(select(func.count()).select_from(Notification)) == 0


def test_schemas_reject_privilege_injection_and_empty_reasons():
    with pytest.raises(ValidationError):
        body(role="admin")
    with pytest.raises(ValidationError):
        decision(note="   ")
    with pytest.raises(ValidationError):
        body(details=" " * 40)


@pytest.mark.asyncio
async def test_history_pagination_and_admin_filter(service):
    for i in range(22):
        service.db.add(
            OwnerAccessRequest(
                user_id=1,
                request_id=str(uuid4()),
                email="u1@example.com",
                details=f"Historical rejected application {i}",
                status="rejected",
                decision_note="Insufficient verification.",
                reviewer_id=3,
                decided_at=datetime.now(UTC),
            )
        )
    await service.db.commit()
    first = await service.page(CUSTOMER)
    second = await service.page(CUSTOMER, offset=20)
    assert len(first.items) == 20 and first.has_next
    assert len(second.items) == 2 and not second.has_next
    assert set(r.id for r in first.items).isdisjoint(r.id for r in second.items)
    assert (await service.page(ADMIN, admin=True, status="pending")).items == []
    assert len((await service.page(ADMIN, admin=True, status="rejected")).items) == 20


@pytest.mark.asyncio
async def test_self_decision_and_demo_decision_rejected(service, monkeypatch):
    row = await service.create(body(), CUSTOMER)
    user = await service.db.scalar(select(User).where(User.id == 1))
    user.role = "admin"
    await service.db.commit()
    with pytest.raises(HTTPException) as error:
        await service.decide(row.id, decision(), CUSTOMER)
    assert error.value.status_code == 403
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    with pytest.raises(HTTPException) as error:
        await service.decide(row.id, decision("rejected"), ADMIN)
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_http_permissions_private_history_and_revoked_bearer(
    service, monkeypatch
):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient

    from app.api.routers.owner_access import router
    from app.core.security import create_access_token
    from app.db.session import get_db

    monkeypatch.setattr(settings, "PROPERTY_RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "APP_ENV", "development")
    app = FastAPI()
    app.include_router(router)

    async def database():
        yield service.db

    app.dependency_overrides[get_db] = database
    customer = {"Authorization": f"Bearer {create_access_token(1)}"}
    admin = {"Authorization": f"Bearer {create_access_token(3)}"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/owner-access/mine")).status_code == 401
        assert (
            await client.get("/admin/owner-access", headers=customer)
        ).status_code == 403
        response = await client.post(
            "/owner-access/requests",
            headers=customer,
            json=body().model_dump(mode="json"),
        )
        assert response.status_code == 201
        rid = response.json()["id"]
        other = {"Authorization": f"Bearer {create_access_token(2)}"}
        assert (await client.get("/owner-access/mine", headers=other)).json()[
            "items"
        ] == []
        assert (
            await client.post(
                f"/admin/owner-access/{rid}/decision",
                headers=other,
                json=decision().model_dump(),
            )
        ).status_code == 403
        assert (
            await client.post(
                f"/admin/owner-access/{rid}/decision",
                headers=admin,
                json=decision().model_dump(),
            )
        ).status_code == 200
        assert (
            await client.get("/owner-access/mine", headers=customer)
        ).status_code == 401
        fresh = {"Authorization": f"Bearer {create_access_token(1, token_version=1)}"}
        result = (await client.get("/owner-access/mine", headers=fresh)).json()
        assert result["items"][0]["status"] == "approved"
        assert "reviewer_id" not in result["items"][0]


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("STAY_TEST_POSTGRES"), reason="Requires PostgreSQL")
async def test_postgres_concurrent_submission_and_competing_decisions(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    schema = "owner_access_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    tables = [
        User.__table__,
        APIKey.__table__,
        Notification.__table__,
        OwnerAccessRequest.__table__,
    ]
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=tables)
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            await db.run_sync(seed)
        data = body()

        async def submit(command):
            async with sessions() as db:
                try:
                    return await OwnerAccessService(db).create(command, CUSTOMER)
                except HTTPException as error:
                    return error

        same = await asyncio.gather(submit(data), submit(data))
        assert same[0].id == same[1].id
        assert (await submit(body())).status_code == 409

        async def decide(command):
            async with sessions() as db:
                try:
                    return await OwnerAccessService(db).decide(
                        same[0].id, command, ADMIN
                    )
                except HTTPException as error:
                    return error

        results = await asyncio.gather(decide(decision()), decide(decision("rejected")))
        assert sum(isinstance(result, HTTPException) for result in results) == 1
        assert [r.status_code for r in results if isinstance(r, HTTPException)] == [409]
        async with sessions() as db:
            row = await db.scalar(select(OwnerAccessRequest))
            user = await db.scalar(select(User).where(User.id == 1))
            key = await db.scalar(select(APIKey))
            assert user.role == ("owner" if row.status == "approved" else "customer")
            assert user.token_version == (1 if row.status == "approved" else 0)
            assert (key.revoked_at is not None) == (row.status == "approved")
            assert await db.scalar(select(func.count()).select_from(Notification)) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()


@pytest.mark.skipif(not os.getenv("STAY_TEST_POSTGRES"), reason="Requires PostgreSQL")
def test_migration_round_trip_in_isolated_schema():
    import runpy
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect, text

    schema = "owner_access_migration_" + uuid4().hex
    engine = create_engine(settings.DATABASE_URL.replace("+asyncpg", "+psycopg2"))
    migration = runpy.run_path(
        str(
            Path(__file__).resolve().parents[1]
            / "alembic/versions/a79b46c120de_owner_access_requests.py"
        )
    )
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(schema))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            User.__table__.create(connection)
            with Operations.context(MigrationContext.configure(connection)):
                migration["upgrade"]()
                assert "owner_access_requests" in inspect(connection).get_table_names(
                    schema=schema
                )
                indexes = inspect(connection).get_indexes(
                    "owner_access_requests", schema=schema
                )
                assert any(
                    i["name"] == "uq_owner_access_pending" and i["unique"]
                    for i in indexes
                )
                migration["downgrade"]()
                assert inspect(connection).get_table_names(schema=schema) == ["users"]
                migration["upgrade"]()
            connection.execute(DropSchema(schema, cascade=True))
    finally:
        engine.dispose()

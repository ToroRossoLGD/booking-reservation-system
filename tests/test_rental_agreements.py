import asyncio
import importlib.util
import os
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.routers.rental_agreements import router
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.rental_agreement import RentalAgreement, RentalCharge, RentalChargeEvent
from app.models.rental_inquiry import RentalInquiry
from app.models.rental_message import RentalMessage
from app.models.user import User
from app.models.venue import Venue
from app.schemas.rental_agreement import AgreementAction, AgreementCreate, ChargeUpdate
from app.services.rental_agreement_service import RentalAgreementService, month_date
from app.services.rental_inquiry_service import RentalInquiryService
from tests import test_rental_inquiries, test_stays
from tests.test_rental_inquiries import OTHER, OWNER, TENANT, inquiry_data

service = test_rental_inquiries.service
TABLES = [
    RentalAgreement.__table__,
    RentalCharge.__table__,
    RentalChargeEvent.__table__,
]
TODAY = date(2026, 11, 4)


def proposal(**changes):
    return AgreementCreate(
        **(
            dict(
                request_id=uuid4(),
                start_date=date(2027, 1, 31),
                months=3,
                monthly_cents=60000,
                deposit_cents=60000,
                notes="Bills paid separately",
            )
            | changes
        )
    )


@pytest.fixture
def agreements(service, monkeypatch):
    session = service.db.scalar.side_effect.__self__
    service.db.get = AsyncMock(side_effect=session.get)
    for table in TABLES:
        table.create(session.get_bind())
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "PROPERTY_RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(
        RentalAgreementService, "today", staticmethod(lambda zone: TODAY)
    )
    return RentalAgreementService(service.db)


async def make_agreement(service, agreements, tenant=TENANT, **changes):
    inquiry = await service.create(1, inquiry_data(), tenant)
    agreement = await agreements.create(inquiry.id, proposal(**changes), OWNER)
    return inquiry, agreement


@pytest.mark.parametrize(
    "start,offset,expected",
    [
        (date(2027, 1, 31), 1, date(2027, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2027, 1, 31), 2, date(2027, 3, 31)),
        (date(2027, 12, 31), 2, date(2028, 2, 29)),
    ],
)
def test_anchor_month_dates(start, offset, expected):
    assert month_date(start, offset) == expected


@pytest.mark.asyncio
async def test_proposal_acceptance_plan_idempotency_and_manual_audit(
    service, agreements
):
    inquiry = await service.create(1, inquiry_data(), TENANT)
    data = proposal()
    agreement = await agreements.create(inquiry.id, data, OWNER)
    assert agreement.end_date == date(2027, 4, 30)
    assert (await agreements.create(inquiry.id, data, OWNER)).id == agreement.id
    assert await agreements.charges(agreement.id, TENANT) == []
    with pytest.raises(HTTPException) as wrong_actor:
        await agreements.act(
            agreement.id, AgreementAction(version=1, action="accept"), OWNER
        )
    assert wrong_actor.value.status_code == 403
    accepted = await agreements.act(
        agreement.id, AgreementAction(version=1, action="accept"), TENANT
    )
    assert accepted.status == "accepted" and accepted.version == 2
    charges = await agreements.charges(agreement.id, OWNER)
    assert [c.sequence for c in charges] == [0, 1, 2, 3]
    assert [c.due_date for c in charges] == [
        date(2027, 1, 31),
        date(2027, 1, 31),
        date(2027, 2, 28),
        date(2027, 3, 31),
    ]
    with pytest.raises(HTTPException) as stale:
        await agreements.act(
            agreement.id, AgreementAction(version=1, action="accept"), TENANT
        )
    assert stale.value.status_code == 409
    assert len(await agreements.charges(agreement.id, TENANT)) == 4
    charge = charges[1]
    with pytest.raises(HTTPException):
        await agreements.record_payment(
            agreement.id, charge.id, ChargeUpdate(version=1, paid=True), TENANT
        )
    changed = await agreements.record_payment(
        agreement.id, charge.id, ChargeUpdate(version=1, paid=True), OWNER
    )
    assert changed.paid and changed.version == 2
    with pytest.raises(HTTPException):
        await agreements.record_payment(
            agreement.id, charge.id, ChargeUpdate(version=1, paid=False), OWNER
        )
    await agreements.record_payment(
        agreement.id, charge.id, ChargeUpdate(version=2, paid=False), OWNER
    )
    events = await agreements.events(agreement.id, charge.id, TENANT)
    assert [(e.paid, e.version) for e in events] == [(False, 3), (True, 2)]


@pytest.mark.asyncio
async def test_private_access_demo_stale_request_and_decline_replacement(
    service, agreements, monkeypatch
):
    inquiry, agreement = await make_agreement(service, agreements)
    for action in (
        agreements.list(inquiry.id, OTHER),
        agreements.charges(agreement.id, OTHER),
        agreements.events(agreement.id, 999, OTHER),
    ):
        with pytest.raises(HTTPException) as denied:
            await action
        assert denied.value.status_code == 404
    with pytest.raises(HTTPException):
        await agreements.create(inquiry.id, proposal(), TENANT)
    with pytest.raises(HTTPException):
        await agreements.create(inquiry.id, proposal(), OWNER)
    with pytest.raises(HTTPException):
        await agreements.create(
            inquiry.id,
            proposal(request_id=agreement.request_id, monthly_cents=1),
            OWNER,
        )
    await agreements.act(
        agreement.id, AgreementAction(version=1, action="decline"), TENANT
    )
    replacement = await agreements.create(inquiry.id, proposal(deposit_cents=0), OWNER)
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    with pytest.raises(HTTPException) as demo:
        await agreements.act(
            replacement.id, AgreementAction(version=1, action="accept"), TENANT
        )
    assert demo.value.status_code == 403
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    await agreements.act(
        replacement.id, AgreementAction(version=1, action="withdraw"), OWNER
    )
    assert len(await agreements.list(inquiry.id, TENANT)) == 2


@pytest.mark.asyncio
async def test_overlapping_acceptance_and_closed_or_transferred_inquiry(
    service, agreements
):
    _, first = await make_agreement(service, agreements)
    second_inquiry, second = await make_agreement(service, agreements, OTHER)
    await agreements.act(first.id, AgreementAction(version=1, action="accept"), TENANT)
    with pytest.raises(HTTPException) as overlap:
        await agreements.act(
            second.id, AgreementAction(version=1, action="accept"), OTHER
        )
    assert overlap.value.status_code == 409
    assert await agreements.charges(second.id, OTHER) == []
    second_inquiry.status = "closed"
    await agreements.db.commit()
    with pytest.raises(HTTPException):
        await agreements.act(
            second.id, AgreementAction(version=1, action="accept"), OTHER
        )
    second_inquiry.status = "open"
    venue = await agreements.db.get(Venue, 1)
    venue.owner_id = 3
    await agreements.db.commit()
    with pytest.raises(HTTPException):
        await agreements.act(
            second.id, AgreementAction(version=1, action="accept"), OTHER
        )


@pytest.mark.asyncio
async def test_acceptance_and_payment_rollback_leave_no_partial_records(
    service, agreements
):
    _, agreement = await make_agreement(service, agreements)
    db = agreements.db
    commit = db.commit
    db.commit = AsyncMock(side_effect=RuntimeError("failed"))
    with pytest.raises(RuntimeError):
        await agreements.act(
            agreement.id, AgreementAction(version=1, action="accept"), TENANT
        )
    await db.rollback()
    db.commit = commit
    agreement_id = agreement.id
    assert (await agreements.get(agreement_id, TENANT)).status == "proposed"
    assert not await agreements.charges(agreement_id, TENANT)
    await agreements.act(
        agreement_id, AgreementAction(version=1, action="accept"), TENANT
    )
    charge_id = (await agreements.charges(agreement_id, TENANT))[0].id
    db.commit = AsyncMock(side_effect=RuntimeError("failed"))
    with pytest.raises(RuntimeError):
        await agreements.record_payment(
            agreement_id, charge_id, ChargeUpdate(version=1, paid=True), OWNER
        )
    await db.rollback()
    db.commit = commit
    assert not (await db.get(RentalCharge, charge_id)).paid
    assert not await agreements.events(agreement_id, charge_id, TENANT)


@pytest.mark.asyncio
async def test_http_verification_validation_and_private_responses(service, agreements):
    inquiry = await service.create(1, inquiry_data(), TENANT)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: agreements.db
    user = await agreements.db.get(User, OWNER.id)
    path = f"/rental-inquiries/{inquiry.id}/agreements"
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get(path)).status_code == 401
        app.dependency_overrides[get_current_user] = lambda: user
        assert (
            await client.post(path, json=proposal().model_dump(mode="json"))
        ).status_code == 403
        user.email_verified_at = datetime.now(UTC)
        await agreements.db.commit()
        for changes in (
            {"months": True},
            {"monthly_cents": 1.5},
            {"deposit_cents": -1},
            {"owner_id": 3},
        ):
            assert (
                await client.post(
                    path, json=proposal().model_dump(mode="json") | changes
                )
            ).status_code == 422
        response = await client.post(path, json=proposal().model_dump(mode="json"))
        assert response.status_code == 201
        assert response.headers["cache-control"] == "private, no-store"
        assert "owner_id" not in response.json() and "tenant_id" not in response.json()
        assert len((await client.get(path)).json()) == 1


def test_migration_roundtrip():
    spec = importlib.util.spec_from_file_location(
        "agreement_migration",
        Path("alembic/versions/e72a93bc8601_rental_agreements.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        assert set(inspect(connection).get_table_names()) == {
            "rental_agreements",
            "rental_charges",
            "rental_charge_events",
        }
        module.downgrade()
        assert not inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("STAY_TEST_POSTGRES") != "1", reason="PostgreSQL opt-in")
async def test_postgres_concurrent_acceptance_and_payment_updates(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(
        RentalAgreementService, "today", staticmethod(lambda zone: TODAY)
    )
    schema = "rental_agreement_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    tables = [
        User.__table__,
        Venue.__table__,
        test_stays.PropertyListing.__table__,
        RentalInquiry.__table__,
        RentalMessage.__table__,
        test_stays.Notification.__table__,
        *TABLES,
    ]
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=tables)
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            await db.run_sync(test_stays.seed)
            listing = await db.get(test_stays.PropertyListing, 1)
            listing.offer_type = "long_term"
            await db.commit()
            service = RentalInquiryService(db)
            agreements = RentalAgreementService(db)
            _, first = await make_agreement(service, agreements)
            _, second = await make_agreement(service, agreements, OTHER)

        async def accept(agreement_id, tenant):
            async with sessions() as db:
                try:
                    await RentalAgreementService(db).act(
                        agreement_id,
                        AgreementAction(version=1, action="accept"),
                        tenant,
                    )
                    return agreement_id
                except HTTPException as error:
                    assert error.status_code == 409
                    return None

        results = await asyncio.gather(
            accept(first.id, TENANT), accept(second.id, OTHER)
        )
        assert sum(result is not None for result in results) == 1
        accepted_id = next(result for result in results if result is not None)
        async with sessions() as db:
            charge_id = (await RentalAgreementService(db).charges(accepted_id, OWNER))[
                0
            ].id

        async def pay():
            async with sessions() as db:
                try:
                    await RentalAgreementService(db).record_payment(
                        accepted_id,
                        charge_id,
                        ChargeUpdate(version=1, paid=True),
                        OWNER,
                    )
                    return True
                except HTTPException as error:
                    assert error.status_code == 409
                    return False

        assert sorted(await asyncio.gather(pay(), pay())) == [False, True]
        async with sessions() as db:
            assert (
                len(
                    await RentalAgreementService(db).events(
                        accepted_id, charge_id, OWNER
                    )
                )
                == 1
            )
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()

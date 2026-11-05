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
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.routers.rental_agreements import router
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.rental_agreement import RentalCharge, RentalTermination
from app.models.user import User
from app.schemas.rental_agreement import (
    AgreementAction,
    ChargeUpdate,
    TerminationCreate,
)
from app.services.rental_agreement_service import RentalAgreementService
from app.services.rental_inquiry_service import RentalInquiryService
from app.services.rental_termination_service import RentalTerminationService
from tests import test_rental_agreements as existing
from tests import test_stays
from tests.test_rental_inquiries import OTHER, OWNER, TENANT

service = existing.service
agreements = existing.agreements


def proposal(**changes):
    return TerminationCreate(
        **(
            dict(
                request_id=uuid4(),
                version=2,
                end_date=date(2027, 2, 28),
                notes="Moving out by agreement",
            )
            | changes
        )
    )


def action(name="accept", version=1):
    return AgreementAction(action=name, version=version)


@pytest.fixture
def terminations(agreements):
    session = agreements.db.scalar.side_effect.__self__
    RentalTermination.__table__.create(session.get_bind())
    return RentalTerminationService(agreements.db)


async def accepted(service, agreements):
    _, row = await existing.make_agreement(service, agreements)
    return await agreements.act(row.id, action(), TENANT)


@pytest.mark.asyncio
async def test_mutual_end_preserves_terms_deposit_paid_history_and_releases_only_tail(
    service, agreements, terminations
):
    agreement = await accepted(service, agreements)
    original = agreement.end_date
    charges = await agreements.charges(agreement.id, TENANT)
    await agreements.record_payment(
        agreement.id, charges[1].id, ChargeUpdate(version=1, paid=True), OWNER
    )
    data = proposal()
    end = await terminations.propose(agreement.id, data, OWNER)
    assert agreement.terminated_on is None
    assert (await terminations.propose(agreement.id, data, OWNER)).id == end.id
    assert (await terminations.history(agreement.id, TENANT))[0].notes == data.notes
    with pytest.raises(HTTPException) as wrong_actor:
        await terminations.decide(agreement.id, end.id, action(), OWNER)
    assert wrong_actor.value.status_code == 403
    result = await terminations.decide(agreement.id, end.id, action(), TENANT)
    assert result.status == "accepted" and result.decided_at and result.version == 2
    assert (
        agreement.terminated_on == date(2027, 2, 28) and agreement.end_date == original
    )
    assert agreement.version == 3 and agreement.months == 3
    charges = await agreements.charges(agreement.id, TENANT)
    assert [bool(c.voided_at) for c in charges] == [False, False, True, True]
    assert (
        charges[1].paid
        and len(await agreements.events(agreement.id, charges[1].id, TENANT)) == 1
    )
    assert charges[2].version == 2
    with pytest.raises(HTTPException) as voided:
        await agreements.record_payment(
            agreement.id, charges[2].id, ChargeUpdate(version=2, paid=True), OWNER
        )
    assert voided.value.status_code == 409
    # The retained deposit and earlier rent can still be reconciled.
    await agreements.record_payment(
        agreement.id, charges[0].id, ChargeUpdate(version=1, paid=True), OWNER
    )
    with pytest.raises(HTTPException):
        await terminations.decide(agreement.id, end.id, action(), TENANT)
    with pytest.raises(HTTPException):
        await terminations.propose(agreement.id, proposal(version=3), OWNER)
    _, overlapping = await existing.make_agreement(
        service, agreements, OTHER, start_date=date(2027, 2, 27)
    )
    with pytest.raises(HTTPException):
        await agreements.act(overlapping.id, action(), OTHER)
    await agreements.act(overlapping.id, action("withdraw"), OWNER)
    adjacent = await agreements.create(
        overlapping.inquiry_id, existing.proposal(start_date=date(2027, 2, 28)), OWNER
    )
    assert (await agreements.act(adjacent.id, action(), OTHER)).status == "accepted"


@pytest.mark.asyncio
async def test_decline_withdraw_idempotency_scope_and_privacy(
    service, agreements, terminations, monkeypatch
):
    agreement = await accepted(service, agreements)
    for operation in (
        terminations.history(agreement.id, OTHER),
        terminations.propose(agreement.id, proposal(), OTHER),
    ):
        with pytest.raises(HTTPException) as denied:
            await operation
        assert denied.value.status_code == 404
    with pytest.raises(HTTPException) as tenant:
        await terminations.propose(agreement.id, proposal(), TENANT)
    assert tenant.value.status_code == 403
    data = proposal()
    end = await terminations.propose(agreement.id, data, OWNER)
    with pytest.raises(HTTPException):
        await terminations.propose(
            agreement.id, proposal(request_id=data.request_id, notes="changed"), OWNER
        )
    with pytest.raises(HTTPException):
        await terminations.propose(agreement.id, proposal(), OWNER)
    await terminations.decide(agreement.id, end.id, action("decline"), TENANT)
    next_end = await terminations.propose(agreement.id, proposal(), OWNER)
    await terminations.decide(agreement.id, next_end.id, action("withdraw"), OWNER)
    assert [r.status for r in await terminations.history(agreement.id, OWNER)] == [
        "withdrawn",
        "declined",
    ]
    assert not agreement.terminated_on and not any(
        c.voided_at for c in await agreements.charges(agreement.id, OWNER)
    )
    assert await terminations.history(agreement.id, OWNER, 10) == []
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    with pytest.raises(HTTPException) as demo:
        await terminations.propose(agreement.id, proposal(), OWNER)
    assert demo.value.status_code == 403


@pytest.mark.asyncio
async def test_dates_stale_versions_and_payment_changes_are_rechecked(
    service, agreements, terminations, monkeypatch
):
    agreement = await accepted(service, agreements)
    for changes in (
        {"end_date": date(2027, 2, 27)},
        {"end_date": agreement.start_date},
        {"end_date": agreement.end_date},
        {"version": 1},
    ):
        with pytest.raises(HTTPException) as invalid:
            await terminations.propose(agreement.id, proposal(**changes), OWNER)
        assert invalid.value.status_code == 409
    row = await terminations.propose(agreement.id, proposal(), OWNER)
    future = (await agreements.charges(agreement.id, OWNER))[2]
    await agreements.record_payment(
        agreement.id, future.id, ChargeUpdate(version=1, paid=True), OWNER
    )
    with pytest.raises(HTTPException):
        await terminations.decide(agreement.id, row.id, action(), TENANT)
    assert row.status == "proposed" and agreement.terminated_on is None
    await agreements.record_payment(
        agreement.id, future.id, ChargeUpdate(version=2, paid=False), OWNER
    )
    monkeypatch.setattr(
        RentalAgreementService, "today", staticmethod(lambda zone: date(2027, 3, 1))
    )
    with pytest.raises(HTTPException):
        await terminations.decide(agreement.id, row.id, action(), TENANT)
    # Expired proposals can always be declined/withdrawn for replacement.
    await terminations.decide(agreement.id, row.id, action("withdraw"), OWNER)


@pytest.mark.asyncio
async def test_termination_commit_failure_rolls_back_plan_and_decision(
    service, agreements, terminations
):
    agreement = await accepted(service, agreements)
    row = await terminations.propose(agreement.id, proposal(), OWNER)
    agreement_id, row_id = agreement.id, row.id
    commit = agreements.db.commit
    agreements.db.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    with pytest.raises(RuntimeError):
        await terminations.decide(agreement_id, row_id, action(), TENANT)
    await agreements.db.rollback()
    agreements.db.commit = commit
    assert (await terminations.history(agreement_id, TENANT))[0].status == "proposed"
    assert (await agreements.get(agreement_id, TENANT)).terminated_on is None
    assert not any(c.voided_at for c in await agreements.charges(agreement_id, TENANT))


@pytest.mark.asyncio
async def test_http_auth_validation_private_response_and_bound_ids(
    service, agreements, terminations
):
    agreement = await accepted(service, agreements)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: agreements.db
    user = await agreements.db.get(User, OWNER.id)
    path = f"/rental-agreements/{agreement.id}/terminations"
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
            {"version": True},
            {"notes": " "},
            {"owner_id": 9},
            {"end_date": "invalid"},
        ):
            assert (
                await client.post(
                    path, json=proposal().model_dump(mode="json") | changes
                )
            ).status_code == 422
        response = await client.post(path, json=proposal().model_dump(mode="json"))
        assert response.status_code == 201
        assert response.headers["cache-control"] == "private, no-store"
        assert (
            "request_id" not in response.json()
            and "agreement_id" not in response.json()
        )
        assert (
            await client.post(
                path + "/9999/decision", json={"version": 1, "action": "withdraw"}
            )
        ).status_code == 404
        assert (await client.get(path + "?offset=-1")).status_code == 422


def test_migration_retains_existing_records_and_roundtrips():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for name in (
            "e72a93bc8601_rental_agreements",
            "f83ba4cd9712_rental_termination",
        ):
            spec = importlib.util.spec_from_file_location(
                name, Path("alembic/versions") / f"{name}.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.op = Operations(MigrationContext.configure(connection))
            module.upgrade()
            if name.startswith("e72"):
                connection.execute(
                    text(
                        "INSERT INTO rental_charges "
                        "(id, agreement_id, sequence, due_date, "
                        "amount_cents, paid, version) "
                        "VALUES (1, 1, 1, '2027-01-31', 60000, 1, 2)"
                    )
                )
        assert connection.execute(
            text("SELECT paid, version, voided_at FROM rental_charges WHERE id=1")
        ).one() == (1, 2, None)
        assert "rental_terminations" in inspect(connection).get_table_names()
        module.downgrade()
        assert connection.execute(
            text("SELECT paid, version FROM rental_charges WHERE id=1")
        ).one() == (1, 2)
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("STAY_TEST_POSTGRES") != "1", reason="PostgreSQL opt-in")
async def test_postgres_payment_and_termination_race(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(
        RentalAgreementService, "today", staticmethod(lambda zone: existing.TODAY)
    )
    schema = "rental_termination_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    tables = [
        User.__table__,
        existing.Venue.__table__,
        test_stays.PropertyListing.__table__,
        existing.RentalInquiry.__table__,
        existing.RentalMessage.__table__,
        test_stays.Notification.__table__,
        *existing.TABLES,
        RentalTermination.__table__,
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
            (await db.get(test_stays.PropertyListing, 1)).offer_type = "long_term"
            await db.commit()
            agreement = await accepted(
                RentalInquiryService(db), RentalAgreementService(db)
            )
            end = await RentalTerminationService(db).propose(
                agreement.id, proposal(), OWNER
            )
            future = (await RentalAgreementService(db).charges(agreement.id, OWNER))[2]

        async def race(pay):
            async with sessions() as db:
                try:
                    if pay:
                        await RentalAgreementService(db).record_payment(
                            agreement.id,
                            future.id,
                            ChargeUpdate(version=1, paid=True),
                            OWNER,
                        )
                    else:
                        await RentalTerminationService(db).decide(
                            agreement.id, end.id, action(), TENANT
                        )
                    return True
                except HTTPException as error:
                    assert error.status_code == 409
                    return False

        assert sorted(await asyncio.gather(race(True), race(False))) == [False, True]
        async with sessions() as db:
            current = await db.get(RentalCharge, future.id)
            assert bool(current.voided_at) != current.paid
            history = await RentalTerminationService(db).history(agreement.id, TENANT)
            assert (history[0].status == "accepted") == bool(current.voided_at)
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()

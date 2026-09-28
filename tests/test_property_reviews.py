import asyncio
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.db.base import Base
from app.models.property_review import PropertyReview
from app.schemas.property_review import (
    PropertyReviewCreate,
    PropertyReviewPage,
    PropertyReviewRead,
)
from app.services.property_review_service import PropertyReviewService
from app.services.stay_service import StayService
from tests import test_stays
from tests.test_stay_migration import load_migration

service = test_stays.service


@pytest.fixture
def reviews(service):
    PropertyReview.__table__.create(service.repository.db.add.__self__.get_bind())
    return PropertyReviewService(service.repository.db)


async def completed(service, **changes):
    stay = await service.create(1, test_stays.booking(), test_stays.GUEST)
    stay.check_in = test_stays.TODAY - timedelta(days=5)
    stay.check_out = test_stays.TODAY - timedelta(days=2)
    for field, value in changes.items():
        setattr(stay, field, value)
    return await service.repository.save(stay)


def review_data(**changes):
    return PropertyReviewCreate(
        **(dict(rating=5, comment="Odlican boravak, sve je bilo uredno.") | changes)
    )


@pytest.mark.asyncio
async def test_verified_review_idempotency_public_privacy_and_pagination(
    service, reviews
):
    first = await completed(service)
    assert await reviews.mine(first.id, test_stays.GUEST) is None
    review = await reviews.create(first.id, review_data(), test_stays.GUEST)
    assert (
        await reviews.create(first.id, review_data(), test_stays.GUEST)
    ).id == review.id
    with pytest.raises(HTTPException) as error:
        await reviews.create(first.id, review_data(rating=4), test_stays.GUEST)
    assert error.value.status_code == 409
    second = await completed(service)
    await reviews.create(second.id, review_data(rating=3), test_stays.GUEST)
    page = PropertyReviewPage(**await reviews.public(1, limit=1))
    assert (page.total, page.average_rating, page.has_next) == (2, 4, True)
    assert page.items[0].rating == 3
    assert set(PropertyReviewRead.model_validate(review).model_dump()) == {
        "id",
        "rating",
        "comment",
        "created_at",
    }
    assert len((await reviews.public(1, offset=1, limit=1))["items"]) == 1
    empty = await reviews.public(2)
    assert empty["total"] == 0 and empty["average_rating"] is None


@pytest.mark.asyncio
async def test_authorization_and_completed_stay_rules(service, reviews, monkeypatch):
    stay = await completed(service)
    for user in (test_stays.OTHER, test_stays.OWNER):
        with pytest.raises(HTTPException) as error:
            await reviews.create(stay.id, review_data(), user)
        assert error.value.status_code == 404
        with pytest.raises(HTTPException):
            await reviews.mine(stay.id, user)
    stay.status = "cancelled"
    with pytest.raises(HTTPException) as error:
        await reviews.create(stay.id, review_data(), test_stays.GUEST)
    assert error.value.status_code == 400
    stay.status = "confirmed"
    monkeypatch.setattr(StayService, "today", staticmethod(lambda zone: stay.check_out))
    with pytest.raises(HTTPException) as error:
        await reviews.create(stay.id, review_data(), test_stays.GUEST)
    assert error.value.status_code == 400
    monkeypatch.setattr(
        StayService,
        "today",
        staticmethod(lambda zone: stay.check_out + timedelta(days=1)),
    )
    assert (await reviews.create(stay.id, review_data(), test_stays.GUEST)).rating == 5


@pytest.mark.asyncio
async def test_unpublished_and_non_nightly_reviews_are_not_public(service, reviews):
    stay = await completed(service)
    await reviews.create(stay.id, review_data(), test_stays.GUEST)
    listing = await service.repository.listing(1)
    for offer, published in [
        ("short_stay", False),
        ("long_term", True),
        ("sale", True),
    ]:
        listing.offer_type = offer
        listing.is_published = published
        await service.repository.db.commit()
        with pytest.raises(HTTPException) as error:
            await reviews.public(1)
        assert error.value.status_code == 404
    assert (await reviews.mine(stay.id, test_stays.GUEST)).rating == 5


@pytest.mark.parametrize(
    "changes",
    [
        {"rating": 0},
        {"rating": 6},
        {"rating": 2.5},
        {"rating": True},
        {"comment": "   "},
        {"comment": "a" * 2001},
        {"user_id": 1},
    ],
)
def test_review_validation(changes):
    with pytest.raises(ValidationError):
        review_data(**changes)


def test_review_migration_roundtrip():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        for table in ("stays", "property_listings"):
            connection.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)"))
            connection.execute(text(f"INSERT INTO {table} VALUES (1)"))
        migration = load_migration(
            "b83e0c435796_create_property_reviews.py",
            Operations(MigrationContext.configure(connection)),
        )
        migration.upgrade()
        assert inspect(connection).get_unique_constraints("property_reviews")[0][
            "column_names"
        ] == ["stay_id"]
        migration.downgrade()
        assert "property_reviews" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT id FROM stays")) == 1
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="PostgreSQL locking test runs in CI"
)
async def test_postgres_concurrent_review_retries(monkeypatch):
    monkeypatch.setattr(
        StayService, "today", staticmethod(lambda zone: test_stays.TODAY)
    )
    schema = "property_review_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    tables = [
        test_stays.User.__table__,
        test_stays.Venue.__table__,
        test_stays.PropertyListing.__table__,
        test_stays.Stay.__table__,
        test_stays.StayBlock.__table__,
        test_stays.Notification.__table__,
        PropertyReview.__table__,
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
            stay = await completed(StayService(db))
            stay_id = stay.id

        async def attempt():
            async with sessions() as db:
                return (
                    await PropertyReviewService(db).create(
                        stay_id, review_data(), test_stays.GUEST
                    )
                ).id

        ids = await asyncio.gather(attempt(), attempt(), attempt())
        assert len(set(ids)) == 1
        async with sessions() as db:
            assert (await PropertyReviewService(db).public(1))["total"] == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await engine.dispose()

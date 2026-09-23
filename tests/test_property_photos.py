import asyncio
import importlib.util
import os
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.routers.property_photos import router
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.models.property_listing import PropertyListing
from app.models.property_photo import PropertyPhoto
from app.models.user import User
from app.models.venue import Venue
from app.schemas.property_listing import PropertyListingPage
from app.schemas.property_photo import PropertyPhotoOrder
from app.services.property_photo_service import PropertyPhotoService, prepare_photo
from tests.test_favorite_properties import seed

OWNER = SimpleNamespace(id=1, role="owner")
OTHER = SimpleNamespace(id=3, role="owner")
TABLES = [
    User.__table__,
    Venue.__table__,
    PropertyListing.__table__,
    PropertyPhoto.__table__,
]


def photo_bytes():
    buffer = BytesIO()
    Image.new("RGB", (40, 30), "red").save(buffer, "PNG")
    return buffer.getvalue()


def upload(data=None):
    return UploadFile(
        file=BytesIO(photo_bytes() if data is None else data), filename="photo.png"
    )


class MemoryStorage:
    def __init__(self):
        self.objects = {}
        self.fail_put = False
        self.fail_delete = False

    def put_object(self, *, Bucket, Key, Body, ContentType):
        assert Bucket == "private-test-photos" and ContentType == "image/jpeg"
        if self.fail_put and Key.endswith(".thumb"):
            raise ClientError({"Error": {"Code": "ServiceUnavailable"}}, "PutObject")
        self.objects[Key] = Body

    def delete_object(self, *, Bucket, Key):
        if self.fail_delete:
            raise ClientError({"Error": {"Code": "ServiceUnavailable"}}, "DeleteObject")
        self.objects.pop(Key, None)

    def get_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        return {"Body": BytesIO(self.objects[Key])}


@pytest.fixture
def storage(monkeypatch):
    store = MemoryStorage()
    monkeypatch.setattr(settings, "PROPERTY_PHOTO_BUCKET", "private-test-photos")
    monkeypatch.setattr(PropertyPhotoService, "storage", lambda self: store)
    return store


@pytest.fixture
def service(storage):
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine, tables=TABLES)
    with Session(engine, expire_on_commit=False) as session:
        seed(session)
        db = MagicMock()
        db.add = session.add
        for method in (
            "commit",
            "rollback",
            "refresh",
            "scalar",
            "scalars",
            "execute",
            "delete",
        ):
            setattr(db, method, AsyncMock(side_effect=getattr(session, method)))
        yield PropertyPhotoService(db)
    engine.dispose()


def test_photo_normalization_rotation_and_metadata_removal():
    image = Image.new("RGB", (40, 30), "red")
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "Private metadata"
    source = BytesIO()
    image.save(source, "JPEG", exif=exif)
    full, thumb, width, height = prepare_photo(source.getvalue())
    assert (width, height) == (30, 40)
    for data in (full, thumb):
        with Image.open(BytesIO(data)) as result:
            assert result.format == "JPEG"
            assert not result.getexif()


def test_photo_resize_limits():
    source = BytesIO()
    Image.new("RGB", (3000, 2000)).save(source, "PNG")
    full, thumb, width, height = prepare_photo(source.getvalue())
    assert max(width, height) == 2560
    assert max(Image.open(BytesIO(thumb)).size) == 640
    assert len(full) > len(thumb)


@pytest.mark.parametrize(
    "data", [b"", b"<svg></svg>", b"\x89PNG\r\n\x1a\ncorrupted", b"GIF89a"]
)
def test_corrupt_or_unsupported_images_are_rejected(data):
    with pytest.raises(HTTPException) as error:
        prepare_photo(data)
    assert error.value.status_code == 415


@pytest.mark.asyncio
async def test_upload_retry_permissions_and_draft_privacy(service, storage):
    request_id = uuid4()
    first = await service.upload(4, upload(), request_id, OWNER)
    assert (await service.upload(4, upload(), request_id, OWNER)).id == first.id
    assert len(storage.objects) == 2
    assert (await service.list(4, OWNER))[0].id == first.id
    assert await service.image(4, first.id, user=OWNER)
    for operation, code in (
        (lambda: service.list(4), 404),
        (lambda: service.image(4, first.id), 404),
        (lambda: service.upload(4, upload(), uuid4(), OTHER), 403),
        (lambda: service.delete(4, first.id, OTHER), 403),
        (
            lambda: service.reorder(4, PropertyPhotoOrder(photo_ids=[first.id]), OTHER),
            403,
        ),
        (lambda: service.upload(4, upload(b"different"), request_id, OWNER), 409),
    ):
        with pytest.raises(HTTPException) as error:
            await operation()
        assert error.value.status_code == code
    assert len(storage.objects) == 2


@pytest.mark.asyncio
async def test_reorder_cover_delete_and_stale_list(service, storage):
    first = await service.upload(1, upload(), uuid4(), OWNER)
    second = await service.upload(1, upload(), uuid4(), OWNER)
    third = await service.upload(2, upload(), uuid4(), OWNER)
    reordered = await service.reorder(
        1, PropertyPhotoOrder(photo_ids=[second.id, first.id]), OWNER
    )
    assert [photo.position for photo in reordered] == [0, 1]
    for ids in ([first.id], [first.id, first.id], [first.id, third.id]):
        with pytest.raises(HTTPException) as error:
            await service.reorder(1, PropertyPhotoOrder(photo_ids=ids), OWNER)
        assert error.value.status_code == 409
    await service.delete(1, second.id, OWNER)
    await service.delete(1, second.id, OWNER)
    assert (await service.list(1))[0].id == first.id
    assert second.object_key not in storage.objects
    with pytest.raises(HTTPException) as error:
        await service.image(1, third.id)
    assert error.value.status_code == 404
    listing = await service.db.scalar(
        select(PropertyListing).where(PropertyListing.id == 1)
    )
    result = await service.enrich_page(
        PropertyListingPage(
            items=[listing], total=1, limit=12, offset=0, has_next=False
        )
    )
    assert result.items[0].photos[0].id == first.id
    assert "object_key" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_upload_limits(service, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_MAX_UPLOAD_BYTES", 8)
    with pytest.raises(HTTPException) as error:
        await service.upload(1, upload(), uuid4(), OWNER)
    assert error.value.status_code == 413
    monkeypatch.setattr(settings, "MEDIA_MAX_UPLOAD_BYTES", 10 * 1024 * 1024)
    monkeypatch.setattr("app.services.property_photo_service.MAX_PIXELS", 10)
    with pytest.raises(HTTPException) as error:
        await service.upload(1, upload(), uuid4(), OWNER)
    assert error.value.status_code == 413


@pytest.mark.asyncio
async def test_storage_failures_and_database_failure_cleanup(service, storage):
    storage.fail_put = True
    with pytest.raises(HTTPException) as error:
        await service.upload(1, upload(), uuid4(), OWNER)
    assert error.value.status_code == 502
    assert not storage.objects and not await service.rows(1)
    storage.fail_put = False
    original_commit = service.db.commit
    service.db.commit = AsyncMock(side_effect=RuntimeError("DB failed"))
    with pytest.raises(RuntimeError):
        await service.upload(1, upload(), uuid4(), OWNER)
    assert not storage.objects
    service.db.commit = original_commit
    photo = await service.upload(1, upload(), uuid4(), OWNER)
    storage.fail_delete = True
    await service.delete(1, photo.id, OWNER)
    assert not await service.rows(1)
    with pytest.raises(HTTPException) as error:
        await service.image(1, photo.id)
    assert error.value.status_code == 404


def test_authenticated_upload_and_image_routes(service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: service.db
    with TestClient(app) as client:
        assert client.get("/owner/properties/4/photos").status_code == 401
        app.dependency_overrides[get_current_user] = lambda: OWNER
        response = client.post(
            "/owner/properties/4/photos",
            data={"request_id": str(uuid4())},
            files={"file": ("wrong.txt", photo_bytes(), "text/plain")},
        )
        assert response.status_code == 201
        photo_id = response.json()["id"]
        assert client.get(f"/properties/4/photos/{photo_id}/image").status_code == 404
        image = client.get(
            f"/owner/properties/4/photos/{photo_id}/image?thumbnail=true"
        )
        assert (
            image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
        )
        assert image.headers["cache-control"] == "private, no-store"
        app.dependency_overrides[get_current_user] = lambda: OTHER
        assert (
            client.get(f"/owner/properties/4/photos/{photo_id}/image").status_code
            == 403
        )


def test_migration_round_trip():
    path = (
        Path(__file__).parents[1]
        / "alembic/versions/d49a6e0f1352_add_property_photos.py"
    )
    spec = importlib.util.spec_from_file_location("property_photos_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=TABLES[:-1])
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert {
            column["name"]
            for column in inspect(connection).get_columns("property_photos")
        } == set(PropertyPhoto.__table__.columns.keys())
        migration.downgrade()
        assert "property_photos" not in inspect(connection).get_table_names()
        assert "property_listings" in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("STAY_TEST_POSTGRES"), reason="CI enables PostgreSQL locking tests"
)
async def test_postgres_uploads_respect_gallery_limit(storage):
    schema = "photos_test_" + uuid4().hex
    engine = create_async_engine(
        settings.DATABASE_URL,
        execution_options={"schema_translate_map": {None: schema}},
    )
    try:
        async with engine.begin() as connection:
            await connection.execute(CreateSchema(schema))
            await connection.run_sync(
                lambda sync: Base.metadata.create_all(sync, tables=TABLES)
            )
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as db:
            await db.run_sync(seed)
            for index in range(11):
                db.add(
                    PropertyPhoto(
                        property_id=1,
                        request_id=str(uuid4()),
                        source_hash="a" * 64,
                        object_key=f"existing/{index}",
                        position=index,
                        width=40,
                        height=30,
                    )
                )
            await db.commit()

        async def attempt():
            async with sessions() as db:
                try:
                    await PropertyPhotoService(db).upload(1, upload(), uuid4(), OWNER)
                    return 201
                except HTTPException as error:
                    await db.rollback()
                    return error.status_code

        assert sorted(await asyncio.gather(attempt(), attempt())) == [201, 409]
        async with sessions() as db:
            assert await db.scalar(select(func.count(PropertyPhoto.id))) == 12
    finally:
        async with engine.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True, if_exists=True))
        await engine.dispose()

import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

from app.models.stay import Stay


def load_migration(name, operations):
    path = Path(__file__).parents[1] / "alembic/versions" / name
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = operations
    return module


def test_nightly_migration_preserves_listings_and_defaults_to_disabled():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE venues (id INTEGER PRIMARY KEY)"))
        operations = Operations(MigrationContext.configure(connection))
        previous = load_migration(
            "c4e9a2b7d610_create_property_listings.py", operations
        )
        previous.upgrade()
        connection.execute(
            text(
                "INSERT INTO property_listings "
                "(id, venue_id, title, description, city, "
                "offer_type, area_sqm, rooms, price_cents, currency, contact_email, "
                "is_published) VALUES (1, 1, 'Original', 'Description', 'Belgrade', "
                "'short_stay', 50, 2, 6500, 'EUR', 'host@example.com', 1)"
            )
        )
        migration = load_migration("d5f0b3c8e721_add_nightly_stays.py", operations)
        migration.upgrade()
        row = connection.execute(
            text(
                "SELECT title, booking_enabled, max_guests, minimum_nights, timezone "
                "FROM property_listings"
            )
        ).one()
        assert tuple(row) == ("Original", 0, 2, 1, "Europe/Belgrade")
        assert {
            item["name"] for item in inspect(connection).get_columns("stays")
        } == set(Stay.__table__.columns.keys())
        migration.downgrade()
        assert "stays" not in inspect(connection).get_table_names()
        assert (
            connection.scalar(text("SELECT title FROM property_listings")) == "Original"
        )
    engine.dispose()

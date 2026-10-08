"""Preview-first provisioning for an isolated, disposable PostgreSQL demo database."""

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.models  # noqa: F401 -- register every application table before reset
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.demo_assets import illustration
from app.models.property_listing import PropertyListing
from app.models.property_photo import PropertyPhoto
from app.models.user import User
from app.models.venue import Venue

GUARD = "bookica_demo_guard"


def validate_target(database, action, apply, confirmation):
    if not settings.DEMO_MODE or not database or not database.endswith("_demo"):
        raise ValueError(
            "Refusing: DEMO_MODE and a dedicated _demo database are required."
        )
    if apply and action == "reset" and confirmation != database:
        raise ValueError(
            "Reset requires --confirm-database with the exact database name."
        )


async def populate(session):
    users = []
    for email, role, password in (
        ("owner@example.com", "owner", settings.DEMO_OWNER_PASSWORD),
        ("guest@example.com", "customer", settings.DEMO_GUEST_PASSWORD),
    ):
        if not 16 <= len(password) <= 72 or len(set(password)) < 8:
            raise ValueError(
                "Set independent generated DEMO_OWNER_PASSWORD and "
                "DEMO_GUEST_PASSWORD (16-72 characters)."
            )
        users.append(
            User(email=email, role=role, hashed_password=hash_password(password))
        )
    if settings.DEMO_OWNER_PASSWORD == settings.DEMO_GUEST_PASSWORD:
        raise ValueError("Owner and guest demo passwords must differ.")
    session.add_all(users)
    await session.flush()
    for title, city, offer, price, area, rooms, key in (
        ("Demo studio uz reku", "Beograd", "short_stay", 6500, 32, 0, "demo/river"),
        ("Demo stan sa terasom", "Novi Sad", "long_term", 55000, 58, 2, "demo/garden"),
        ("Demo porodični stan", "Niš", "sale", 12500000, 76, 3, "demo/home"),
    ):
        venue = Venue(
            name=title, address="Izmišljena demo adresa", owner_id=users[0].id
        )
        session.add(venue)
        await session.flush()
        listing = PropertyListing(
            venue_id=venue.id,
            title=title,
            city=city,
            offer_type=offer,
            description=(
                "Izmišljeni oglas za probu aplikacije. Slika je ilustracija, "
                "ne fotografija stvarne nekretnine. Ne unosite stvarne lične podatke."
            ),
            area_sqm=area,
            rooms=rooms,
            price_cents=price,
            currency="EUR",
            contact_email="owner@example.com",
            is_published=True,
            first_published_at=datetime.now(UTC),
            booking_enabled=offer == "short_stay",
            check_in_time="14:00" if offer == "short_stay" else None,
            check_out_time="11:00" if offer == "short_stay" else None,
            property_type="apartment",
            furnishing="furnished",
            minimum_rental_months=6 if offer == "long_term" else None,
        )
        session.add(listing)
        await session.flush()
        session.add(
            PropertyPhoto(
                property_id=listing.id,
                request_id=str(uuid4()),
                source_hash=hashlib.sha256(illustration(key)).hexdigest(),
                object_key=key,
                position=0,
                width=960,
                height=640,
            )
        )
    await session.flush()


async def provision(action, apply=False, confirmation=None):
    database = make_url(settings.DATABASE_URL).database
    validate_target(database, action, apply, confirmation)
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    tables = sorted(Base.metadata.tables)
    quoted = ", ".join('public."' + name + '"' for name in tables)
    try:
        async with engine.begin() as connection:
            actual = await connection.scalar(text("SELECT current_database()"))
            if actual != database:
                raise ValueError(
                    "Connected database does not match the configured target."
                )
            await connection.execute(text("SELECT pg_advisory_xact_lock(72140319)"))
            known = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
                        )
                    )
                ).scalars()
            )
            if (
                known - set(tables) - {"alembic_version", GUARD}
                or not set(tables) <= known
            ):
                raise ValueError(
                    "Unexpected schema: migrate a dedicated empty demo database first."
                )
            if apply:
                await connection.execute(
                    text(f"LOCK TABLE {quoted} IN ACCESS EXCLUSIVE MODE")
                )
            rows = sum(
                [
                    await connection.scalar(
                        text(f'SELECT count(*) FROM public."{name}"')
                    )
                    for name in tables
                ]
            )
            initialized = (
                GUARD in known
                and await connection.scalar(
                    text("SELECT marker FROM public.bookica_demo_guard WHERE id=1")
                )
                == "bookica-demo-v1"
            )
            if action == "reset" and not initialized:
                raise ValueError(
                    "Reset refused: database was not initialized by this demo tool."
                )
            if action == "seed" and rows:
                if initialized:
                    return {"action": "unchanged", "rows": rows}
                raise ValueError("Seed refused: application tables are not empty.")
            if not apply:
                return {
                    "action": action,
                    "apply": False,
                    "rows_affected": rows,
                    "database": database,
                }
            if action == "reset":
                # Preserve sequences: old tokens cannot authenticate newly seeded users.
                # No CASCADE: unknown external dependencies must stop the operation.
                await connection.execute(
                    text(f"TRUNCATE TABLE {quoted} CONTINUE IDENTITY")
                )
            async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                await populate(session)
            if not initialized:
                await connection.execute(
                    text(
                        "CREATE TABLE public.bookica_demo_guard "
                        "(id integer PRIMARY KEY, marker text NOT NULL)"
                    )
                )
                await connection.execute(
                    text(
                        "INSERT INTO public.bookica_demo_guard "
                        "VALUES (1, 'bookica-demo-v1')"
                    )
                )
            return {"action": action, "apply": True, "listings": 3, "accounts": 2}
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed", "reset"])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-database")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                asyncio.run(provision(args.action, args.apply, args.confirm_database))
            )
        )
    except Exception:
        # Database/driver exceptions can include connection credentials or SQL data.
        parser.exit(
            1,
            "Demo operation refused or failed. Check mode, target, migrations, "
            "marker, empty tables and password settings. No credentials are printed.\n",
        )


if __name__ == "__main__":
    main()

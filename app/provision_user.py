"""Operator-only role changes: python -m app.provision_user --help.

Requires trusted shell/database access. No public HTTP endpoint is provided.
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.models.api_key import APIKey
from app.models.user import User, UserRole


async def change_role(db, user_id, email, expected_role, role, *, apply=False):
    user = await db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or user.email != email:
        raise ValueError("User ID/email pair does not match an existing account")
    if user.role != expected_role:
        raise ValueError("Current role differs from --expected-role; inspect and retry")
    if role not in {item.value for item in UserRole}:
        raise ValueError("Unknown target role")
    changed = user.role != role
    result = {
        "user_id": user.id,
        "previous_role": user.role,
        "target_role": role,
        "applied": apply and changed,
        "changed": changed,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if apply and changed:
        user.role = role
        user.token_version += 1
        # Existing API keys must not inherit newly granted privileges.
        await db.execute(
            update(APIKey)
            .where(APIKey.user_id == user.id, APIKey.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await db.commit()
    else:
        await db.rollback()
    return result


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--user-id", type=int, required=True)
    command.add_argument("--email", required=True)
    command.add_argument(
        "--expected-role", choices=[r.value for r in UserRole], required=True
    )
    command.add_argument("--role", choices=[r.value for r in UserRole], required=True)
    command.add_argument(
        "--apply", action="store_true", help="Commit; default is dry run"
    )
    return command


async def run(args):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings

    # Separate engine: do not echo SQL or connection credentials to the operator log.
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            print(
                json.dumps(
                    await change_role(
                        db,
                        args.user_id,
                        args.email,
                        args.expected_role,
                        args.role,
                        apply=args.apply,
                    )
                )
            )
    finally:
        await engine.dispose()


def main():
    args = parser().parse_args()
    try:
        asyncio.run(run(args))
    except ValueError as error:
        raise SystemExit(str(error)) from None
    except Exception:
        raise SystemExit(
            "Provisioning failed; check database access and migrations"
        ) from None


if __name__ == "__main__":
    main()

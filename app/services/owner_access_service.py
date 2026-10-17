from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update

from app.core.config import settings
from app.models.api_key import APIKey
from app.models.notification import Notification
from app.models.owner_access_request import OwnerAccessRequest
from app.models.user import User
from app.schemas.owner_access import OwnerAccessPage, OwnerAccessRead


class OwnerAccessService:
    def __init__(self, db):
        self.db = db

    def writable(self):
        if settings.DEMO_MODE:
            raise HTTPException(403, "Owner access changes are disabled in demo mode")

    async def admin(self, actor):
        current = await self.db.scalar(
            select(User)
            .where(User.id == actor.id)
            .execution_options(populate_existing=True)
        )
        if current is None or current.role != "admin":
            raise HTTPException(403, "Administrator access required")

    async def page(self, actor, *, admin=False, status=None, offset=0):
        if admin:
            await self.admin(actor)
        query = select(OwnerAccessRequest)
        if not admin:
            query = query.where(OwnerAccessRequest.user_id == actor.id)
        if status:
            query = query.where(OwnerAccessRequest.status == status)
        rows = (
            await self.db.scalars(
                query.order_by(OwnerAccessRequest.id.desc()).offset(offset).limit(21)
            )
        ).all()
        return OwnerAccessPage(
            items=[OwnerAccessRead.model_validate(row) for row in rows[:20]],
            has_next=len(rows) > 20,
        )

    async def create(self, data, actor):
        self.writable()
        try:
            user = await self.db.scalar(
                select(User)
                .where(User.id == actor.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if user is None or user.role != "customer" or not user.email_verified:
                raise HTTPException(403, "A verified customer account is required")
            existing = await self.db.scalar(
                select(OwnerAccessRequest).where(
                    OwnerAccessRequest.user_id == user.id,
                    OwnerAccessRequest.request_id == str(data.request_id),
                )
            )
            if existing:
                if existing.details != data.details:
                    raise HTTPException(
                        409, "Request ID already used with different details"
                    )
                result = OwnerAccessRead.model_validate(existing)
                await self.db.rollback()
                return result
            latest = await self.db.scalar(
                select(OwnerAccessRequest)
                .where(OwnerAccessRequest.user_id == user.id)
                .order_by(OwnerAccessRequest.id.desc())
                .limit(1)
            )
            if latest and latest.status == "pending":
                raise HTTPException(409, "A request is already pending")
            if latest and latest.created_at.replace(tzinfo=UTC) > datetime.now(
                UTC
            ) - timedelta(hours=24):
                raise HTTPException(
                    429,
                    "Wait before submitting another request",
                    headers={"Retry-After": "86400"},
                )
            row = OwnerAccessRequest(
                user_id=user.id,
                email=user.email,
                details=data.details,
                request_id=str(data.request_id),
            )
            self.db.add(row)
            await self.db.flush()
            result = OwnerAccessRead.model_validate(row)
            await self.db.commit()
            return result
        except Exception:
            await self.db.rollback()
            raise

    async def decide(self, request_id, data, actor):
        self.writable()
        await self.admin(actor)
        try:
            candidate = await self.db.scalar(
                select(OwnerAccessRequest).where(OwnerAccessRequest.id == request_id)
            )
            if candidate is None:
                raise HTTPException(404, "Request not found")
            if candidate.user_id == actor.id:
                raise HTTPException(403, "Self approval is not allowed")
            # Same lock order as submission and operator role provisioning.
            user = await self.db.scalar(
                select(User)
                .where(User.id == candidate.user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            row = await self.db.scalar(
                select(OwnerAccessRequest)
                .where(OwnerAccessRequest.id == request_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if row.status != "pending":
                if (
                    row.status == data.action
                    and row.decision_note == data.note
                    and row.reviewer_id == actor.id
                ):
                    result = OwnerAccessRead.model_validate(row)
                    await self.db.rollback()
                    return result
                raise HTTPException(409, "A decision already exists; refresh the queue")
            now = datetime.now(UTC)
            if data.action == "approved":
                if (
                    user.role != "customer"
                    or not user.email_verified
                    or user.email != row.email
                ):
                    raise HTTPException(
                        409, "Account changed; approval is no longer valid"
                    )
                user.role = "owner"
                user.token_version += 1
                await self.db.execute(
                    update(APIKey)
                    .where(APIKey.user_id == user.id, APIKey.revoked_at.is_(None))
                    .values(revoked_at=now)
                )
            row.status = data.action
            row.decision_note = data.note
            row.decided_at = now
            row.reviewer_id = actor.id
            self.db.add(
                Notification(
                    user_id=user.id,
                    title="Odluka o vlasničkom pristupu",
                    message=(
                        "Zahtev je odobren. Prijavi se ponovo za vlasnički pristup. "
                        if data.action == "approved"
                        else "Zahtev je odbijen. "
                    )
                    + data.note,
                    action_path="/owner-access",
                    deduplication_key=f"owner-access:{row.id}:decision",
                )
            )
            await self.db.flush()
            result = OwnerAccessRead.model_validate(row)
            await self.db.commit()
            return result
        except Exception:
            await self.db.rollback()
            raise

from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.promotion import Promotion
from app.models.reservation import AttendanceStatus, Reservation, ReservationStatus
from app.models.resource import Resource
from app.models.user import User
from app.models.venue import Venue


class ReservationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        reservation: Reservation,
    ) -> Reservation:
        self.db.add(reservation)
        await self.db.commit()
        await self.db.refresh(reservation)
        return reservation

    async def create_with_conflict_lock(
        self,
        reservation: Reservation,
        promotion_redemptions: int = 0,
    ) -> Reservation | None:
        if reservation.idempotency_key is not None:
            await self.db.execute(
                select(User.id)
                .where(User.id == reservation.user_id)
                .with_for_update()
            )

            existing_result = await self.db.execute(
                select(Reservation).where(
                    Reservation.user_id == reservation.user_id,
                    Reservation.idempotency_key == reservation.idempotency_key,
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing is not None:
                if (
                    existing.idempotency_request_hash
                    != reservation.idempotency_request_hash
                ):
                    await self.db.rollback()
                    raise IdempotencyKeyConflict
                await self.db.rollback()
                return existing

        resource_result = await self.db.execute(
            select(Resource)
            .where(Resource.id == reservation.resource_id)
            .with_for_update()
        )

        resource = resource_result.scalar_one_or_none()

        if resource is None:
            await self.db.rollback()
            return None

        if reservation.promotion_id is not None:
            promotion_result = await self.db.execute(
                select(Promotion)
                .where(Promotion.id == reservation.promotion_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            promotion = promotion_result.scalar_one_or_none()
            if (
                promotion is None
                or not promotion.is_active
                or promotion.venue_id != resource.venue_id
                or not promotion.valid_from <= datetime.now(UTC) < promotion.valid_until
                or (
                    promotion.max_redemptions is not None
                    and promotion.redemption_count + promotion_redemptions
                    > promotion.max_redemptions
                )
            ):
                await self.db.rollback()
                raise PromotionRedemptionUnavailable
            promotion.redemption_count += promotion_redemptions

        conflict_result = await self.db.execute(
            select(Reservation.id)
            .where(
                Reservation.resource_id == reservation.resource_id,
                Reservation.status.in_(["pending", "confirmed"]),
                Reservation.start_time < reservation.end_time,
                Reservation.end_time > reservation.start_time,
            )
            .limit(1)
        )

        has_conflict = conflict_result.scalar_one_or_none() is not None

        if has_conflict:
            await self.db.rollback()
            return None

        self.db.add(reservation)

        await self.db.commit()
        await self.db.refresh(reservation)

        return reservation

    async def create_series_with_conflict_lock(
        self,
        reservations: list[Reservation],
    ) -> list[Reservation] | None:
        if not reservations:
            return []

        resource_id = reservations[0].resource_id
        resource_result = await self.db.execute(
            select(Resource).where(Resource.id == resource_id).with_for_update()
        )

        resource = resource_result.scalar_one_or_none()
        if resource is None:
            await self.db.rollback()
            return None

        promotion_id = reservations[0].promotion_id
        if promotion_id is not None:
            promotion_result = await self.db.execute(
                select(Promotion)
                .where(Promotion.id == promotion_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            promotion = promotion_result.scalar_one_or_none()
            if (
                promotion is None
                or not promotion.is_active
                or promotion.venue_id != resource.venue_id
                or not promotion.valid_from <= datetime.now(UTC) < promotion.valid_until
                or (
                    promotion.max_redemptions is not None
                    and promotion.redemption_count + len(reservations)
                    > promotion.max_redemptions
                )
            ):
                await self.db.rollback()
                raise PromotionRedemptionUnavailable
            promotion.redemption_count += len(reservations)

        overlap_checks = [
            and_(
                Reservation.start_time < reservation.end_time,
                Reservation.end_time > reservation.start_time,
            )
            for reservation in reservations
        ]
        conflict_result = await self.db.execute(
            select(Reservation.id)
            .where(
                Reservation.resource_id == resource_id,
                Reservation.status.in_(["pending", "confirmed"]),
                or_(*overlap_checks),
            )
            .limit(1)
        )

        if conflict_result.scalar_one_or_none() is not None:
            await self.db.rollback()
            return None

        self.db.add_all(reservations)
        await self.db.commit()

        for reservation in reservations:
            await self.db.refresh(reservation)

        return reservations

    async def reschedule_with_conflict_lock(
        self,
        reservation: Reservation,
        start_time: datetime,
        end_time: datetime,
    ) -> Reservation | None:
        resource_result = await self.db.execute(
            select(Resource)
            .where(Resource.id == reservation.resource_id)
            .with_for_update()
        )

        if resource_result.scalar_one_or_none() is None:
            await self.db.rollback()
            return None

        conflict_result = await self.db.execute(
            select(Reservation.id)
            .where(
                Reservation.resource_id == reservation.resource_id,
                Reservation.id != reservation.id,
                Reservation.status.in_(["pending", "confirmed"]),
                Reservation.start_time < end_time,
                Reservation.end_time > start_time,
            )
            .limit(1)
        )

        if conflict_result.scalar_one_or_none() is not None:
            await self.db.rollback()
            return None

        reservation.start_time = start_time
        reservation.end_time = end_time

        await self.db.commit()
        await self.db.refresh(reservation)

        return reservation

    async def get_user_reservations(
        self,
        user_id: int,
        limit: int,
        offset: int,
        status: str | None = None,
    ) -> list[Reservation]:
        query = select(Reservation).where(Reservation.user_id == user_id)

        if status is not None:
            query = query.where(Reservation.status == status)

        query = (
            query.order_by(Reservation.start_time.desc()).limit(limit).offset(offset)
        )

        result = await self.db.execute(query)

        return list(result.scalars().all())

    async def has_conflicting_reservation(
        self,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> bool:
        return (
            await self.get_conflicting_reservation(resource_id, start_time, end_time)
        ) is not None

    async def get_conflicting_reservation(
        self,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Reservation | None:
        result = await self.db.execute(
            select(Reservation).where(
                and_(
                    Reservation.resource_id == resource_id,
                    Reservation.status.in_(["pending", "confirmed"]),
                    Reservation.start_time < end_time,
                    Reservation.end_time > start_time,
                )
            )
        )

        return result.scalar_one_or_none()

    async def get_by_id(
        self,
        reservation_id: int,
    ) -> Reservation | None:
        result = await self.db.execute(
            select(Reservation).where(Reservation.id == reservation_id)
        )

        return result.scalar_one_or_none()

    async def get_by_idempotency_key(
        self,
        user_id: int,
        idempotency_key: str,
    ) -> Reservation | None:
        result = await self.db.execute(
            select(Reservation).where(
                Reservation.user_id == user_id,
                Reservation.idempotency_key == idempotency_key,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(
        self,
        reservation_id: int,
    ) -> Reservation | None:
        result = await self.db.execute(
            select(Reservation)
            .where(Reservation.id == reservation_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_series_id(
        self,
        recurrence_series_id: str,
    ) -> list[Reservation]:
        result = await self.db.execute(
            select(Reservation)
            .where(Reservation.recurrence_series_id == recurrence_series_id)
            .order_by(Reservation.start_time)
        )
        return list(result.scalars().all())

    async def update(
        self,
        reservation: Reservation,
    ) -> Reservation:
        await self.db.commit()
        await self.db.refresh(reservation)
        return reservation

    async def get_by_owner_id(
        self,
        owner_id: int,
    ):
        result = await self.db.execute(
            select(Reservation, Resource, Venue)
            .join(Resource, Reservation.resource_id == Resource.id)
            .join(Venue, Resource.venue_id == Venue.id)
            .where(Venue.owner_id == owner_id)
            .order_by(Reservation.start_time)
        )

        return result.all()

    async def get_expired_pending_reservations(
        self,
        older_than,
    ) -> list[Reservation]:
        result = await self.db.execute(
            select(Reservation).where(
                Reservation.status == "pending",
                Reservation.created_at < older_than,
            )
        )

        return list(result.scalars().all())

    async def get_no_show_candidates(
        self,
        started_before: datetime,
    ) -> list[Reservation]:
        result = await self.db.execute(
            select(Reservation)
            .where(
                Reservation.status == ReservationStatus.CONFIRMED.value,
                Reservation.attendance_status == AttendanceStatus.SCHEDULED.value,
                Reservation.start_time < started_before,
            )
            .with_for_update(skip_locked=True)
        )
        return list(result.scalars().all())

    async def count_user_reservations(
        self,
        user_id: int,
        status: str | None = None,
    ) -> int:
        query = select(func.count(Reservation.id)).where(Reservation.user_id == user_id)

        if status is not None:
            query = query.where(Reservation.status == status)

        result = await self.db.execute(query)

        return result.scalar_one()


class PromotionRedemptionUnavailable(Exception):
    pass


class IdempotencyKeyConflict(Exception):
    pass

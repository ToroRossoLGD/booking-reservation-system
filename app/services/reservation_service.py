import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import (
    build_available_slots_cache_key,
    delete_available_slots_cache_for_resource,
    get_cache,
    set_cache,
)
from app.core.config import settings
from app.core.security import create_check_in_token, decode_check_in_token
from app.models.payment import PaymentStatus
from app.models.reservation import AttendanceStatus, Reservation, ReservationStatus
from app.models.reservation_event import ReservationEvent, ReservationEventType
from app.models.user import User
from app.repositories.availability_exception_repository import (
    AvailabilityExceptionRepository,
)
from app.repositories.availability_rule_repository import (
    AvailabilityRuleRepository,
)
from app.repositories.payment_repository import PaymentRepository
from app.repositories.promotion_repository import PromotionRepository
from app.repositories.reservation_event_repository import ReservationEventRepository
from app.repositories.reservation_repository import (
    IdempotencyKeyConflict,
    PromotionRedemptionUnavailable,
    ReservationRepository,
)
from app.repositories.resource_repository import ResourceRepository
from app.repositories.venue_repository import VenueRepository
from app.repositories.venue_staff_repository import VenueStaffRepository
from app.schemas.reservation import (
    RecurringReservationCreate,
    RecurringSeriesCancellationRequest,
    ReservationCreate,
    ReservationReschedule,
)
from app.services.notification_service import NotificationService
from app.services.pricing_service import PricingService
from app.services.waitlist_service import WaitlistService


class ReservationService:
    def __init__(self, db: AsyncSession):
        self.reservation_repository = ReservationRepository(db)
        self.reservation_event_repository = ReservationEventRepository(db)
        self.resource_repository = ResourceRepository(db)
        self.venue_repository = VenueRepository(db)
        self.venue_staff_repository = VenueStaffRepository(db)
        self.notification_service = NotificationService(db)
        self.availability_rule_repository = AvailabilityRuleRepository(db)
        self.availability_exception_repository = AvailabilityExceptionRepository(db)
        self.payment_repository = PaymentRepository(db)
        self.promotion_repository = PromotionRepository(db)
        self.waitlist_service = WaitlistService(db)
        self.db = db

    async def _record_event(
        self,
        reservation: Reservation,
        event_type: ReservationEventType,
        actor: User | None,
        previous_status: str | None = None,
        details: dict | None = None,
    ) -> ReservationEvent:
        return await self.reservation_event_repository.create(
            ReservationEvent(
                reservation_id=reservation.id,
                event_type=event_type.value,
                actor_id=actor.id if actor is not None else None,
                actor_role=actor.role if actor is not None else "system",
                previous_status=previous_status,
                new_status=reservation.status,
                details=details or {},
            )
        )

    async def _resolve_promotion(
        self,
        promotion_code: str | None,
        venue_id: int,
        redemption_count: int = 1,
    ):
        if promotion_code is None:
            return None

        promotion = await self.promotion_repository.get_by_code(promotion_code)
        now = datetime.now(UTC)
        if promotion is None:
            raise HTTPException(status_code=404, detail="Promotion code not found")
        if promotion.venue_id != venue_id:
            raise HTTPException(
                status_code=400, detail="Promotion is not valid for this venue"
            )
        if not promotion.is_active:
            raise HTTPException(status_code=400, detail="Promotion is inactive")
        if not promotion.valid_from <= now < promotion.valid_until:
            raise HTTPException(
                status_code=400, detail="Promotion is outside its validity period"
            )
        if (
            promotion.max_redemptions is not None
            and promotion.redemption_count + redemption_count
            > promotion.max_redemptions
        ):
            raise HTTPException(
                status_code=409, detail="Promotion redemption limit reached"
            )
        return promotion

    async def _get_cancellation_policy(self, venue_id: int) -> tuple[int, int]:
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )
        return (
            venue.free_cancellation_hours,
            venue.late_cancellation_refund_percent,
        )

    async def _validate_booking_rules(
        self,
        venue_id: int,
        occurrences: list[tuple[datetime, datetime]],
        current_user: User,
        additional_reservations: int | None = None,
    ) -> None:
        venue = await self.venue_repository.get_by_id(venue_id)
        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )

        current_time = datetime.now(UTC)
        earliest_allowed = current_time + timedelta(
            minutes=venue.minimum_booking_notice_minutes
        )
        latest_allowed = current_time + timedelta(
            days=venue.maximum_advance_booking_days
        )

        for index, (start_time, end_time) in enumerate(occurrences, start=1):
            prefix = f"Occurrence {index}: " if len(occurrences) > 1 else ""
            if start_time.tzinfo is None or end_time.tzinfo is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{prefix}reservation times must include a timezone",
                )
            if start_time < earliest_allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"{prefix}reservation requires at least "
                        f"{venue.minimum_booking_notice_minutes} minutes notice"
                    ),
                )
            if start_time > latest_allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"{prefix}reservation cannot be made more than "
                        f"{venue.maximum_advance_booking_days} days in advance"
                    ),
                )

            duration_minutes = int((end_time - start_time).total_seconds() / 60)
            if duration_minutes < venue.minimum_booking_duration_minutes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"{prefix}reservation must be at least "
                        f"{venue.minimum_booking_duration_minutes} minutes"
                    ),
                )
            if duration_minutes > venue.maximum_booking_duration_minutes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"{prefix}reservation cannot exceed "
                        f"{venue.maximum_booking_duration_minutes} minutes"
                    ),
                )

        await self.reservation_repository.lock_user_for_booking_rules(current_user.id)
        active_count = await self.reservation_repository.count_active_for_user_at_venue(
            user_id=current_user.id,
            venue_id=venue_id,
            current_time=current_time,
        )
        reservation_delta = (
            len(occurrences)
            if additional_reservations is None
            else additional_reservations
        )
        if (
            active_count + reservation_delta
            > venue.max_active_reservations_per_customer
        ):
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Venue active reservation limit would be exceeded "
                    f"({venue.max_active_reservations_per_customer} per customer)"
                ),
            )

    @staticmethod
    def _idempotency_request_hash(data: ReservationCreate) -> str:
        payload = {
            "resource_id": data.resource_id,
            "start_time": data.start_time.isoformat(),
            "end_time": data.end_time.isoformat(),
            "promotion_code": data.promotion_code,
        }
        # Preserve hashes created before group bookings for the default party size.
        if data.party_size != 1:
            payload["party_size"] = data.party_size
        encoded_payload = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(encoded_payload).hexdigest()

    @staticmethod
    def _ensure_idempotency_payload_matches(
        reservation: Reservation,
        request_hash: str,
    ) -> None:
        if reservation.idempotency_request_hash != request_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used with a different request",
            )

    @staticmethod
    def _price_details(resource, start_time, end_time, promotion=None) -> dict:
        base_amount = PricingService.calculate_amount_cents(
            resource.hourly_rate_cents, start_time, end_time
        )
        discount_amount = (
            PricingService.calculate_discount_cents(
                base_amount, promotion.discount_percent
            )
            if promotion is not None
            else 0
        )
        return {
            "base_amount_cents": base_amount,
            "discount_amount_cents": discount_amount,
            "quoted_amount_cents": max(0, base_amount - discount_amount),
            "quoted_currency": resource.currency,
            "promotion_id": promotion.id if promotion is not None else None,
            "promotion_code": promotion.code if promotion is not None else None,
            "promotion_discount_percent": (
                promotion.discount_percent if promotion is not None else None
            ),
        }

    async def _has_availability_exception(
        self,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> bool:
        return await self.availability_exception_repository.has_overlapping_exception(
            resource_id=resource_id,
            start_time=start_time,
            end_time=end_time,
        )

    async def _is_within_availability_rules(
        self,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> bool:
        if start_time.date() != end_time.date():
            return False

        weekday = start_time.weekday()

        rules = await self.availability_rule_repository.get_for_resource_and_weekday(
            resource_id=resource_id,
            weekday=weekday,
        )

        requested_start_time = start_time.time()
        requested_end_time = end_time.time()

        return any(
            rule.start_time <= requested_start_time
            and rule.end_time >= requested_end_time
            for rule in rules
        )

    async def create_reservation(
        self,
        data: ReservationCreate,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
        idempotency_key: str | None = None,
    ) -> Reservation:

        request_hash = self._idempotency_request_hash(data)
        if idempotency_key is not None:
            existing = await self.reservation_repository.get_by_idempotency_key(
                current_user.id, idempotency_key
            )
            if existing is not None:
                self._ensure_idempotency_payload_matches(existing, request_hash)
                return existing

        if data.start_time >= data.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time",
            )

        resource = await self.resource_repository.get_by_id(data.resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )
        if data.party_size > resource.capacity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Party size exceeds resource capacity ({resource.capacity})",
            )

        promotion = await self._resolve_promotion(
            data.promotion_code, resource.venue_id
        )
        (
            free_cancellation_hours,
            late_refund_percent,
        ) = await self._get_cancellation_policy(resource.venue_id)
        await self._validate_booking_rules(
            resource.venue_id,
            [(data.start_time, data.end_time)],
            current_user,
        )

        is_within_rules = await self._is_within_availability_rules(
            resource_id=data.resource_id,
            start_time=data.start_time,
            end_time=data.end_time,
        )

        if not is_within_rules:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=("Requested time is outside the resource availability rules"),
            )

        has_conflict = await self.reservation_repository.has_conflicting_reservation(
            resource_id=data.resource_id,
            start_time=data.start_time,
            end_time=data.end_time,
            party_size=data.party_size,
        )

        if has_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resource does not have enough capacity for this time slot",
            )
        has_exception = await self._has_availability_exception(
            resource_id=data.resource_id,
            start_time=data.start_time,
            end_time=data.end_time,
        )

        if has_exception:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=("Resource is unavailable during the requested time"),
            )

        price_details = self._price_details(
            resource, data.start_time, data.end_time, promotion
        )
        reservation = Reservation(
            start_time=data.start_time,
            end_time=data.end_time,
            user_id=current_user.id,
            resource_id=data.resource_id,
            party_size=data.party_size,
            hold_expires_at=datetime.now(UTC)
            + timedelta(minutes=settings.RESERVATION_EXPIRE_MINUTES),
            idempotency_key=idempotency_key,
            idempotency_request_hash=(
                request_hash if idempotency_key is not None else None
            ),
            cancellation_free_hours=free_cancellation_hours,
            cancellation_late_refund_percent=late_refund_percent,
            **price_details,
        )

        try:
            created_reservation = (
                await self.reservation_repository.create_with_conflict_lock(
                    reservation,
                    promotion_redemptions=1 if promotion is not None else 0,
                )
            )
        except PromotionRedemptionUnavailable as error:
            raise HTTPException(
                status_code=409,
                detail="Promotion became unavailable",
            ) from error
        except IdempotencyKeyConflict as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used with a different request",
            ) from error

        if created_reservation is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resource no longer has enough capacity for this time slot",
            )

        if created_reservation is not reservation:
            return created_reservation

        await self._record_event(
            created_reservation,
            ReservationEventType.CREATED,
            current_user,
            details={
                "start_time": created_reservation.start_time.isoformat(),
                "end_time": created_reservation.end_time.isoformat(),
                "resource_id": created_reservation.resource_id,
                "party_size": created_reservation.party_size,
            },
        )

        await delete_available_slots_cache_for_resource(data.resource_id)

        await self.notification_service.create_notification(
            user_id=current_user.id,
            title="Reservation created",
            message=f"Your reservation #{created_reservation.id} has been created.",
            user_email=current_user.email,
            background_tasks=background_tasks,
        )

        return created_reservation

    async def create_recurring_reservations(
        self,
        data: RecurringReservationCreate,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict:
        if data.start_time.tzinfo is None or data.end_time.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reservation times must include a timezone",
            )

        if data.start_time >= data.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time",
            )

        if data.start_time <= datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Recurring reservations must start in the future",
            )

        resource = await self.resource_repository.get_by_id(data.resource_id)
        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )
        if data.party_size > resource.capacity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Party size exceeds resource capacity ({resource.capacity})",
            )

        promotion = await self._resolve_promotion(
            data.promotion_code,
            resource.venue_id,
            redemption_count=data.occurrence_count,
        )
        (
            free_cancellation_hours,
            late_refund_percent,
        ) = await self._get_cancellation_policy(resource.venue_id)

        interval = timedelta(days=1 if data.frequency == "daily" else 7)
        occurrences = [
            (data.start_time + interval * index, data.end_time + interval * index)
            for index in range(data.occurrence_count)
        ]
        await self._validate_booking_rules(
            resource.venue_id,
            occurrences,
            current_user,
        )

        for index, (start_time, end_time) in enumerate(occurrences, start=1):
            if not await self._is_within_availability_rules(
                resource_id=data.resource_id,
                start_time=start_time,
                end_time=end_time,
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Occurrence {index} is outside the resource availability rules"
                    ),
                )

            if await self._has_availability_exception(
                resource_id=data.resource_id,
                start_time=start_time,
                end_time=end_time,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Occurrence {index} overlaps an availability exception",
                )

            if await self.reservation_repository.has_conflicting_reservation(
                resource_id=data.resource_id,
                start_time=start_time,
                end_time=end_time,
                party_size=data.party_size,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Occurrence {index} conflicts with another reservation",
                )

        series_id = str(uuid4())
        reservations = [
            Reservation(
                start_time=start_time,
                end_time=end_time,
                user_id=current_user.id,
                resource_id=data.resource_id,
                party_size=data.party_size,
                hold_expires_at=datetime.now(UTC)
                + timedelta(minutes=settings.RESERVATION_EXPIRE_MINUTES),
                recurrence_series_id=series_id,
                cancellation_free_hours=free_cancellation_hours,
                cancellation_late_refund_percent=late_refund_percent,
                **self._price_details(resource, start_time, end_time, promotion),
            )
            for start_time, end_time in occurrences
        ]
        try:
            created_reservations = (
                await self.reservation_repository.create_series_with_conflict_lock(
                    reservations
                )
            )
        except PromotionRedemptionUnavailable as error:
            raise HTTPException(
                status_code=409,
                detail="Promotion became unavailable",
            ) from error

        if created_reservations is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="One or more occurrences became unavailable",
            )

        for created_reservation in created_reservations:
            await self._record_event(
                created_reservation,
                ReservationEventType.CREATED,
                current_user,
                details={
                    "start_time": created_reservation.start_time.isoformat(),
                    "end_time": created_reservation.end_time.isoformat(),
                    "resource_id": created_reservation.resource_id,
                    "party_size": created_reservation.party_size,
                    "recurrence_series_id": series_id,
                },
            )

        await delete_available_slots_cache_for_resource(data.resource_id)
        await self.notification_service.create_notification(
            user_id=current_user.id,
            title="Recurring reservations created",
            message=(
                f"Your series of {len(created_reservations)} reservations "
                f"has been created. Series: {series_id}."
            ),
            user_email=current_user.email,
            background_tasks=background_tasks,
        )

        return {
            "recurrence_series_id": series_id,
            "occurrence_count": len(created_reservations),
            "reservations": created_reservations,
        }

    async def get_recurring_reservations(
        self,
        recurrence_series_id: str,
        current_user: User,
    ) -> dict:
        reservations = await self.reservation_repository.get_by_series_id(
            recurrence_series_id
        )
        if not reservations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recurring reservation series not found",
            )

        if current_user.role != "admin" and any(
            reservation.user_id != current_user.id for reservation in reservations
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can view only your own recurring reservation series",
            )

        return {
            "recurrence_series_id": recurrence_series_id,
            "occurrence_count": len(reservations),
            "reservations": reservations,
        }

    async def cancel_recurring_reservations(
        self,
        recurrence_series_id: str,
        data: RecurringSeriesCancellationRequest,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict:
        series = await self.get_recurring_reservations(
            recurrence_series_id=recurrence_series_id,
            current_user=current_user,
        )
        reservations = series["reservations"]
        current_time = datetime.now(UTC)
        cancellation_cutoff = data.cancel_from or current_time
        if cancellation_cutoff < current_time:
            cancellation_cutoff = current_time

        eligible_statuses = {
            ReservationStatus.PENDING.value,
            ReservationStatus.CONFIRMED.value,
        }
        eligible = [
            reservation
            for reservation in reservations
            if reservation.status in eligible_statuses
            and reservation.start_time > current_time
            and reservation.start_time >= cancellation_cutoff
        ]

        cancelled_reservations = []
        total_refund_amount_cents = 0
        total_cancellation_fee_cents = 0

        for reservation in eligible:
            try:
                result = await self.cancel_reservation(
                    reservation_id=reservation.id,
                    current_user=current_user,
                    background_tasks=background_tasks,
                    recurring_series_id=recurrence_series_id,
                )
            except HTTPException as error:
                # A concurrent cancellation or state transition is safe to skip.
                if error.status_code in {
                    status.HTTP_400_BAD_REQUEST,
                    status.HTTP_404_NOT_FOUND,
                }:
                    continue
                raise

            cancelled_reservations.append(result["reservation"])
            total_refund_amount_cents += result["refund_amount_cents"]
            total_cancellation_fee_cents += result["cancellation_fee_cents"]

        cancelled_count = len(cancelled_reservations)
        return {
            "recurrence_series_id": recurrence_series_id,
            "occurrence_count": len(reservations),
            "cancelled_count": cancelled_count,
            "skipped_count": len(reservations) - cancelled_count,
            "total_refund_amount_cents": total_refund_amount_cents,
            "total_cancellation_fee_cents": total_cancellation_fee_cents,
            "cancelled_reservations": cancelled_reservations,
        }

    async def get_my_reservations(
        self,
        current_user: User,
        limit: int,
        offset: int,
        status_filter: str | None = None,
    ) -> dict:
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="limit must be between 1 and 100",
            )

        if offset < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="offset must be greater than or equal to 0",
            )

        valid_statuses = {
            ReservationStatus.PENDING.value,
            ReservationStatus.CONFIRMED.value,
            ReservationStatus.CANCELLED.value,
            ReservationStatus.COMPLETED.value,
            ReservationStatus.EXPIRED.value,
        }

        if status_filter is not None and status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reservation status filter",
            )

        items = await self.reservation_repository.get_user_reservations(
            user_id=current_user.id,
            limit=limit,
            offset=offset,
            status=status_filter,
        )

        total = await self.reservation_repository.count_user_reservations(
            user_id=current_user.id,
            status=status_filter,
        )

        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_next": offset + limit < total,
        }

    async def get_reservation(
        self,
        reservation_id: int,
        current_user: User,
    ) -> Reservation:
        reservation = await self.reservation_repository.get_by_id(reservation_id)

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found",
            )

        if current_user.role == "admin" or reservation.user_id == current_user.id:
            return reservation

        await self._ensure_owner_can_manage_reservation(
            reservation=reservation,
            current_user=current_user,
            allowed_staff_roles={"manager"},
        )

        return reservation

    async def get_check_in_pass(
        self,
        reservation_id: int,
        current_user: User,
    ) -> dict:
        reservation = await self.reservation_repository.get_by_id(reservation_id)
        if reservation is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        if current_user.role != "admin" and reservation.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You can get a check-in pass only for your own reservation",
            )
        if reservation.status != ReservationStatus.CONFIRMED.value:
            raise HTTPException(
                status_code=400,
                detail="Only confirmed reservations have check-in passes",
            )
        if reservation.attendance_status == AttendanceStatus.NO_SHOW.value:
            raise HTTPException(
                status_code=400, detail="Reservation was marked as a no-show"
            )

        expires_at = reservation.start_time + timedelta(
            minutes=settings.NO_SHOW_GRACE_MINUTES
        )
        if expires_at <= datetime.now(UTC):
            raise HTTPException(status_code=400, detail="Check-in pass has expired")

        valid_from = reservation.start_time - timedelta(
            minutes=settings.CHECK_IN_EARLY_MINUTES
        )
        return {
            "reservation_id": reservation.id,
            "token": create_check_in_token(
                reservation_id=reservation.id,
                expires_at=expires_at,
            ),
            "valid_from": valid_from,
            "expires_at": expires_at,
        }

    async def check_in_reservation(
        self,
        token: str,
        current_user: User,
    ) -> Reservation:
        reservation_id = decode_check_in_token(token)
        if reservation_id is None:
            raise HTTPException(
                status_code=400, detail="Invalid or expired check-in pass"
            )

        reservation = await self.reservation_repository.get_by_id_for_update(
            reservation_id
        )
        if reservation is None:
            raise HTTPException(
                status_code=400, detail="Invalid or expired check-in pass"
            )

        await self._ensure_owner_can_manage_reservation(
            reservation,
            current_user,
            allowed_staff_roles={"manager", "check_in_agent"},
        )

        if reservation.status != ReservationStatus.CONFIRMED.value:
            raise HTTPException(
                status_code=400, detail="Only confirmed reservations can check in"
            )
        if reservation.attendance_status == AttendanceStatus.CHECKED_IN.value:
            return reservation
        if reservation.attendance_status == AttendanceStatus.NO_SHOW.value:
            raise HTTPException(
                status_code=400, detail="Reservation was marked as a no-show"
            )

        now = datetime.now(UTC)
        earliest_check_in = reservation.start_time - timedelta(
            minutes=settings.CHECK_IN_EARLY_MINUTES
        )
        if now < earliest_check_in:
            raise HTTPException(
                status_code=400,
                detail=f"Check-in opens at {earliest_check_in.isoformat()}",
            )
        latest_check_in = reservation.start_time + timedelta(
            minutes=settings.NO_SHOW_GRACE_MINUTES
        )
        if now > latest_check_in:
            raise HTTPException(status_code=400, detail="Check-in window has closed")

        reservation.attendance_status = AttendanceStatus.CHECKED_IN.value
        reservation.checked_in_at = now
        return await self.reservation_repository.update(reservation)

    async def mark_no_shows(self) -> dict:
        now = datetime.now(UTC)
        cutoff = now - timedelta(minutes=settings.NO_SHOW_GRACE_MINUTES)
        reservations = await self.reservation_repository.get_no_show_candidates(cutoff)
        for reservation in reservations:
            reservation.attendance_status = AttendanceStatus.NO_SHOW.value
            reservation.no_show_marked_at = now
        if reservations:
            await self.db.commit()
        return {"no_show_count": len(reservations)}

    async def reschedule_reservation(
        self,
        reservation_id: int,
        data: ReservationReschedule,
        current_user: User,
    ) -> Reservation:
        reservation = await self.reservation_repository.get_by_id(reservation_id)

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found",
            )

        if current_user.role != "admin" and reservation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can reschedule only your own reservations",
            )

        if reservation.status not in {
            ReservationStatus.PENDING.value,
            ReservationStatus.CONFIRMED.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending or confirmed reservations can be rescheduled",
            )

        if data.start_time.tzinfo is None or data.end_time.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reservation times must include a timezone",
            )

        if data.start_time >= data.end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time",
            )

        if data.start_time <= datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A reservation must be rescheduled to a future time",
            )

        is_within_rules = await self._is_within_availability_rules(
            resource_id=reservation.resource_id,
            start_time=data.start_time,
            end_time=data.end_time,
        )

        if not is_within_rules:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requested time is outside the resource availability rules",
            )

        if await self._has_availability_exception(
            resource_id=reservation.resource_id,
            start_time=data.start_time,
            end_time=data.end_time,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resource is unavailable during the requested time",
            )

        previous_start_time = reservation.start_time
        previous_end_time = reservation.end_time

        resource = await self.resource_repository.get_by_id(reservation.resource_id)
        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        await self._validate_booking_rules(
            resource.venue_id,
            [(data.start_time, data.end_time)],
            current_user,
            additional_reservations=0,
        )

        reservation.base_amount_cents = PricingService.calculate_amount_cents(
            resource.hourly_rate_cents,
            data.start_time,
            data.end_time,
        )
        reservation.discount_amount_cents = (
            PricingService.calculate_discount_cents(
                reservation.base_amount_cents,
                reservation.promotion_discount_percent,
            )
            if reservation.promotion_discount_percent is not None
            else 0
        )
        reservation.quoted_amount_cents = max(
            0,
            reservation.base_amount_cents - reservation.discount_amount_cents,
        )
        reservation.quoted_currency = resource.currency

        updated_reservation = (
            await self.reservation_repository.reschedule_with_conflict_lock(
                reservation=reservation,
                start_time=data.start_time,
                end_time=data.end_time,
            )
        )

        if updated_reservation is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Resource is already booked for this time slot",
            )

        await self._record_event(
            updated_reservation,
            ReservationEventType.RESCHEDULED,
            current_user,
            previous_status=updated_reservation.status,
            details={
                "previous_start_time": previous_start_time.isoformat(),
                "previous_end_time": previous_end_time.isoformat(),
                "new_start_time": updated_reservation.start_time.isoformat(),
                "new_end_time": updated_reservation.end_time.isoformat(),
            },
        )

        await delete_available_slots_cache_for_resource(reservation.resource_id)

        await self.waitlist_service.notify_next_for_slot(
            resource_id=reservation.resource_id,
            start_time=previous_start_time,
            end_time=previous_end_time,
        )

        await self.notification_service.create_notification(
            user_id=reservation.user_id,
            title="Reservation rescheduled",
            message=(
                f"Your reservation #{reservation.id} was rescheduled to "
                f"{data.start_time.isoformat()}."
            ),
        )

        return updated_reservation

    def _get_refund_percentage(
        self,
        reservation: Reservation,
        current_time: datetime,
    ) -> int:
        if reservation.start_time <= current_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=("A reservation cannot be cancelled after its start time"),
            )

        time_until_start = reservation.start_time - current_time
        hours_until_start = time_until_start.total_seconds() / 3600

        free_cancellation_hours = (
            reservation.cancellation_free_hours
            if reservation.cancellation_free_hours is not None
            else settings.FREE_CANCELLATION_HOURS
        )
        late_refund_percent = (
            reservation.cancellation_late_refund_percent
            if reservation.cancellation_late_refund_percent is not None
            else settings.LATE_CANCELLATION_REFUND_PERCENT
        )

        if hours_until_start >= free_cancellation_hours:
            return 100

        return late_refund_percent

    async def cancel_reservation(
        self,
        reservation_id: int,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
        recurring_series_id: str | None = None,
    ) -> dict:
        reservation = await self.reservation_repository.get_by_id(reservation_id)

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found",
            )

        is_admin = current_user.role == "admin"
        is_owner = reservation.user_id == current_user.id

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can cancel only your own reservations",
            )

        if reservation.status == ReservationStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reservation is already cancelled",
            )

        if reservation.status == ReservationStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Completed reservations cannot be cancelled",
            )

        if reservation.status == ReservationStatus.EXPIRED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Expired reservations cannot be cancelled",
            )

        current_time = datetime.now(UTC)

        refund_percentage = self._get_refund_percentage(
            reservation=reservation,
            current_time=current_time,
        )

        payment = await self.payment_repository.get_by_reservation_id(reservation_id)

        refund_amount_cents = 0
        cancellation_fee_cents = 0

        if payment is not None and payment.status == PaymentStatus.PAID.value:
            refund_amount_cents = payment.amount_cents * refund_percentage // 100

            cancellation_fee_cents = payment.amount_cents - refund_amount_cents

            payment.refunded_amount_cents = refund_amount_cents
            payment.cancellation_fee_cents = cancellation_fee_cents
            payment.refunded_at = current_time

            if refund_percentage == 100:
                payment.status = PaymentStatus.REFUNDED.value
            else:
                payment.status = PaymentStatus.PARTIALLY_REFUNDED.value

        previous_status = reservation.status
        reservation.status = ReservationStatus.CANCELLED.value

        try:
            await self.db.commit()
            await self.db.refresh(reservation)

            if payment is not None:
                await self.db.refresh(payment)
        except Exception:
            await self.db.rollback()
            raise

        await self._record_event(
            reservation,
            ReservationEventType.CANCELLED,
            current_user,
            previous_status=previous_status,
            details={
                "refund_percentage": refund_percentage,
                "refund_amount_cents": refund_amount_cents,
                "cancellation_fee_cents": cancellation_fee_cents,
                "applied_free_cancellation_hours": (
                    reservation.cancellation_free_hours
                ),
                "applied_late_refund_percent": (
                    reservation.cancellation_late_refund_percent
                ),
                "recurring_series_id": recurring_series_id,
            },
        )

        await delete_available_slots_cache_for_resource(reservation.resource_id)

        await self.waitlist_service.notify_next_for_slot(
            resource_id=reservation.resource_id,
            start_time=reservation.start_time,
            end_time=reservation.end_time,
        )

        if refund_amount_cents > 0:
            message = (
                f"Your reservation #{reservation.id} was cancelled. "
                f"Refund: {refund_amount_cents} "
                f"{payment.currency} cents."
            )
        else:
            message = f"Your reservation #{reservation.id} has been cancelled."

        await self.notification_service.create_notification(
            user_id=reservation.user_id,
            title="Reservation cancelled",
            message=message,
            user_email=current_user.email,
            background_tasks=background_tasks,
        )

        return {
            "reservation": reservation,
            "payment": payment,
            "refund_percentage": (
                refund_percentage
                if payment is not None
                and payment.status
                in {
                    PaymentStatus.REFUNDED.value,
                    PaymentStatus.PARTIALLY_REFUNDED.value,
                }
                else 0
            ),
            "refund_amount_cents": refund_amount_cents,
            "cancellation_fee_cents": cancellation_fee_cents,
            "applied_free_cancellation_hours": (reservation.cancellation_free_hours),
            "applied_late_refund_percent": (
                reservation.cancellation_late_refund_percent
            ),
        }

    async def check_availability(
        self,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
        party_size: int = 1,
    ) -> dict:
        if start_time >= end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time",
            )

        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )
        if party_size < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="party_size must be greater than 0",
            )

        is_within_rules = await self._is_within_availability_rules(
            resource_id=resource_id,
            start_time=start_time,
            end_time=end_time,
        )

        if not is_within_rules:
            return {
                "resource_id": resource_id,
                "start_time": start_time,
                "end_time": end_time,
                "available": False,
                "requested_capacity": party_size,
                "remaining_capacity": 0,
            }
        has_exception = await self._has_availability_exception(
            resource_id=resource_id,
            start_time=start_time,
            end_time=end_time,
        )

        if has_exception:
            return {
                "resource_id": resource_id,
                "start_time": start_time,
                "end_time": end_time,
                "available": False,
                "requested_capacity": party_size,
                "remaining_capacity": 0,
            }

        (
            _capacity,
            remaining_capacity,
        ) = await self.reservation_repository.get_capacity_availability(
            resource_id=resource_id,
            start_time=start_time,
            end_time=end_time,
        )

        return {
            "resource_id": resource_id,
            "start_time": start_time,
            "end_time": end_time,
            "available": party_size <= remaining_capacity,
            "requested_capacity": party_size,
            "remaining_capacity": remaining_capacity,
        }

    async def get_price_quote(
        self,
        resource_id: int,
        start_time: datetime,
        end_time: datetime,
        promotion_code: str | None = None,
    ) -> dict:
        if start_time.tzinfo is None or end_time.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reservation times must include a timezone",
            )

        if start_time >= end_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start time must be before end time",
            )

        resource = await self.resource_repository.get_by_id(resource_id)
        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        promotion = await self._resolve_promotion(promotion_code, resource.venue_id)
        details = self._price_details(resource, start_time, end_time, promotion)

        duration_minutes = int((end_time - start_time).total_seconds() / 60)
        return {
            "resource_id": resource_id,
            "start_time": start_time,
            "end_time": end_time,
            "duration_minutes": duration_minutes,
            "hourly_rate_cents": resource.hourly_rate_cents,
            "amount_cents": details["quoted_amount_cents"],
            "currency": resource.currency,
            "base_amount_cents": details["base_amount_cents"],
            "discount_amount_cents": details["discount_amount_cents"],
            "promotion_code": details["promotion_code"],
            "promotion_discount_percent": details["promotion_discount_percent"],
        }

    async def _ensure_owner_can_manage_reservation(
        self,
        reservation: Reservation,
        current_user: User,
        allowed_staff_roles: set[str],
    ) -> None:
        if current_user.role == "admin":
            return

        resource = await self.resource_repository.get_by_id(reservation.resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        venue = await self.venue_repository.get_by_id(resource.venue_id)

        if venue is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venue not found",
            )

        if venue.owner_id == current_user.id:
            return
        if await self.venue_staff_repository.has_role(
            venue.id, current_user.id, allowed_staff_roles
        ):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this reservation",
        )

    async def confirm_reservation(
        self,
        reservation_id: int,
        current_user: User,
    ) -> Reservation:
        reservation = await self.reservation_repository.get_by_id(reservation_id)

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found",
            )

        await self._ensure_owner_can_manage_reservation(
            reservation,
            current_user,
            allowed_staff_roles={"manager"},
        )

        if reservation.status != ReservationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending reservations can be confirmed",
            )

        if (
            reservation.hold_expires_at is not None
            and reservation.hold_expires_at <= datetime.now(UTC)
        ):
            reservation.status = ReservationStatus.EXPIRED.value
            await self.reservation_repository.update(reservation)
            await self._record_event(
                reservation,
                ReservationEventType.EXPIRED,
                actor=None,
                previous_status=ReservationStatus.PENDING.value,
                details={"reason": "booking_hold_elapsed"},
            )
            await delete_available_slots_cache_for_resource(reservation.resource_id)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reservation hold has expired",
            )

        previous_status = reservation.status
        reservation.status = ReservationStatus.CONFIRMED.value
        reservation.hold_expires_at = None

        updated_reservation = await self.reservation_repository.update(reservation)

        await self._record_event(
            updated_reservation,
            ReservationEventType.CONFIRMED,
            current_user,
            previous_status=previous_status,
        )

        await self.notification_service.create_notification(
            user_id=reservation.user_id,
            title="Reservation confirmed",
            message=f"Your reservation #{reservation.id} has been confirmed.",
        )

        await delete_available_slots_cache_for_resource(reservation.resource_id)

        return updated_reservation

    async def complete_reservation(
        self,
        reservation_id: int,
        current_user: User,
    ) -> Reservation:
        reservation = await self.reservation_repository.get_by_id(reservation_id)

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found",
            )

        await self._ensure_owner_can_manage_reservation(
            reservation,
            current_user,
            allowed_staff_roles={"manager"},
        )

        if reservation.status != ReservationStatus.CONFIRMED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only confirmed reservations can be completed",
            )

        if reservation.attendance_status != AttendanceStatus.CHECKED_IN.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only checked-in reservations can be completed",
            )

        previous_status = reservation.status
        reservation.status = ReservationStatus.COMPLETED.value

        updated_reservation = await self.reservation_repository.update(reservation)

        await self._record_event(
            updated_reservation,
            ReservationEventType.COMPLETED,
            current_user,
            previous_status=previous_status,
        )

        await self.notification_service.create_notification(
            user_id=reservation.user_id,
            title="Reservation completed",
            message=f"Your reservation #{reservation.id} has been completed.",
        )

        await delete_available_slots_cache_for_resource(reservation.resource_id)

        return updated_reservation

    async def get_available_slots(
        self,
        resource_id: int,
        selected_date: date,
        slot_minutes: int,
    ) -> list[dict]:
        if slot_minutes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="slot_minutes must be greater than 0",
            )

        cache_key = build_available_slots_cache_key(
            resource_id=resource_id,
            selected_date=selected_date,
            slot_minutes=slot_minutes,
        )

        cached_slots = await get_cache(cache_key)

        if cached_slots is not None:
            return cached_slots

        resource = await self.resource_repository.get_by_id(resource_id)

        if resource is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resource not found",
            )

        weekday = selected_date.weekday()

        rules = await self.availability_rule_repository.get_for_resource_and_weekday(
            resource_id=resource_id,
            weekday=weekday,
        )

        slots: list[dict] = []
        slot_delta = timedelta(minutes=slot_minutes)

        for rule in rules:
            rule_start = datetime.combine(
                selected_date,
                rule.start_time,
                tzinfo=UTC,
            )
            rule_end = datetime.combine(
                selected_date,
                rule.end_time,
                tzinfo=UTC,
            )

            current_start = rule_start

            while current_start + slot_delta <= rule_end:
                current_end = current_start + slot_delta

                exception_repository = self.availability_exception_repository

                has_exception = await exception_repository.has_overlapping_exception(
                    resource_id=resource_id,
                    start_time=current_start,
                    end_time=current_end,
                )

                (
                    _capacity,
                    remaining_capacity,
                ) = await self.reservation_repository.get_capacity_availability(
                    resource_id=resource_id,
                    start_time=current_start,
                    end_time=current_end,
                )

                slots.append(
                    {
                        "start_time": current_start,
                        "end_time": current_end,
                        "available": remaining_capacity > 0 and not has_exception,
                        "remaining_capacity": (
                            0 if has_exception else remaining_capacity
                        ),
                    }
                )

                current_start = current_end

        await set_cache(
            key=cache_key,
            value=slots,
        )

        return slots

    async def expire_pending_reservations(self) -> dict:
        cutoff_time = datetime.now(UTC) - timedelta(
            minutes=settings.RESERVATION_EXPIRE_MINUTES
        )

        expired_reservations = (
            await self.reservation_repository.get_expired_pending_reservations(
                older_than=cutoff_time
            )
        )

        expired_count = 0

        for reservation in expired_reservations:
            reservation.status = ReservationStatus.EXPIRED.value

            await self.reservation_repository.update(reservation)

            await self._record_event(
                reservation,
                ReservationEventType.EXPIRED,
                actor=None,
                previous_status=ReservationStatus.PENDING.value,
            )

            await delete_available_slots_cache_for_resource(reservation.resource_id)

            expired_count += 1

        return {"expired_count": expired_count}

    async def get_reservation_timeline(
        self,
        reservation_id: int,
        current_user: User,
    ) -> dict:
        reservation = await self.get_reservation(reservation_id, current_user)
        events = await self.reservation_event_repository.get_for_reservation(
            reservation.id
        )
        return {"reservation_id": reservation.id, "events": events}

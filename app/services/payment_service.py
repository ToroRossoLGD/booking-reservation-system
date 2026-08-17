from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment, PaymentStatus
from app.models.reservation import ReservationStatus
from app.models.reservation_event import ReservationEvent, ReservationEventType
from app.models.user import User
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_event_repository import ReservationEventRepository
from app.repositories.reservation_repository import ReservationRepository
from app.services.notification_service import NotificationService


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.payment_repository = PaymentRepository(db)
        self.reservation_repository = ReservationRepository(db)
        self.reservation_event_repository = ReservationEventRepository(db)
        self.notification_service = NotificationService(db)

    async def get_reservation_payment(
        self,
        reservation_id: int,
        current_user: User,
    ) -> Payment:
        reservation = await self.reservation_repository.get_by_id(reservation_id)

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found",
            )

        if reservation.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can view payments only for your own reservations",
            )

        payment = await self.payment_repository.get_by_reservation_id(reservation_id)

        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )

        return payment

    async def pay_for_reservation(
        self,
        reservation_id: int,
        current_user: User,
        background_tasks: BackgroundTasks | None = None,
    ) -> Payment:
        reservation = await self.reservation_repository.get_by_id(reservation_id)

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reservation not found",
            )

        if reservation.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can pay only for your own reservations",
            )

        if reservation.status != ReservationStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending reservations can be paid",
            )

        if (
            reservation.quoted_amount_cents is None
            or reservation.quoted_currency is None
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reservation does not have a price quote",
            )

        existing_payment = await self.payment_repository.get_by_reservation_id(
            reservation_id
        )

        if existing_payment and existing_payment.status == PaymentStatus.PAID.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Reservation is already paid",
            )

        payment = existing_payment

        if payment is None:
            payment = Payment(
                reservation_id=reservation_id,
                amount_cents=reservation.quoted_amount_cents,
                currency=reservation.quoted_currency,
                status=PaymentStatus.PENDING.value,
                provider="mock",
            )
            payment = await self.payment_repository.create(payment)

        payment.status = PaymentStatus.PAID.value
        payment.amount_cents = reservation.quoted_amount_cents
        payment.currency = reservation.quoted_currency

        paid_payment = await self.payment_repository.update(payment)

        previous_status = reservation.status
        reservation.status = ReservationStatus.CONFIRMED.value
        await self.reservation_repository.update(reservation)

        await self.reservation_event_repository.create(
            ReservationEvent(
                reservation_id=reservation.id,
                event_type=ReservationEventType.PAID.value,
                actor_id=current_user.id,
                actor_role=current_user.role,
                previous_status=previous_status,
                new_status=reservation.status,
                details={
                    "payment_id": paid_payment.id,
                    "amount_cents": paid_payment.amount_cents,
                    "currency": paid_payment.currency,
                },
            )
        )

        await self.notification_service.create_notification(
            user_id=current_user.id,
            title="Payment successful",
            message=f"Payment for reservation #{reservation.id} was successful.",
            user_email=current_user.email,
            background_tasks=background_tasks,
        )

        return paid_payment

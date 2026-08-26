from asyncio import to_thread
from datetime import UTC, datetime

import stripe
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.payment import Payment, PaymentStatus
from app.models.reservation import ReservationStatus
from app.models.user import User
from app.repositories.payment_repository import PaymentRepository
from app.repositories.reservation_repository import ReservationRepository


class StripeService:
    def __init__(self, db: AsyncSession):
        self.payments = PaymentRepository(db)
        self.reservations = ReservationRepository(db)

    @staticmethod
    def _configure() -> None:
        if not settings.STRIPE_SECRET_KEY:
            raise HTTPException(
                status_code=503, detail="Stripe test mode is not configured"
            )
        try:
            settings.validate_stripe_safety()
        except ValueError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if not settings.STRIPE_SECRET_KEY.startswith(("sk_test_", "sk_live_")):
            raise HTTPException(status_code=503, detail="Stripe secret key is invalid")
        stripe.api_key = settings.STRIPE_SECRET_KEY

    async def create_checkout(self, reservation_id: int, current_user: User) -> dict:
        self._configure()
        reservation = await self.reservations.get_by_id(reservation_id)
        if reservation is None:
            raise HTTPException(status_code=404, detail="Reservation not found")
        if reservation.user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="You can pay only for your own reservations"
            )
        if reservation.status != ReservationStatus.PENDING.value:
            raise HTTPException(
                status_code=400, detail="Only pending reservations can be paid"
            )
        if reservation.hold_expires_at and reservation.hold_expires_at <= datetime.now(
            UTC
        ):
            raise HTTPException(status_code=409, detail="Reservation hold has expired")

        payment = await self.payments.get_by_reservation_id(reservation_id)
        if payment and payment.status == PaymentStatus.PAID.value:
            raise HTTPException(status_code=409, detail="Reservation is already paid")
        if payment is None:
            payment = await self.payments.create(
                Payment(
                    reservation_id=reservation.id,
                    amount_cents=reservation.quoted_amount_cents,
                    currency=reservation.quoted_currency,
                    status=PaymentStatus.PENDING.value,
                    provider="stripe",
                )
            )

        session = await to_thread(
            stripe.checkout.Session.create,
            mode="payment",
            client_reference_id=str(reservation.id),
            metadata={
                "reservation_id": str(reservation.id),
                "payment_id": str(payment.id),
            },
            line_items=[
                {
                    "price_data": {
                        "currency": reservation.quoted_currency.lower(),
                        "unit_amount": reservation.quoted_amount_cents,
                        "product_data": {"name": f"Reservation #{reservation.id}"},
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{settings.FRONTEND_URL}/?payment=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_URL}/?payment=cancelled",
        )
        payment.provider = "stripe"
        payment.provider_session_id = session.id
        await self.payments.update(payment)
        return {
            "payment_id": payment.id,
            "checkout_session_id": session.id,
            "checkout_url": session.url,
            "test_mode": settings.STRIPE_SECRET_KEY.startswith("sk_test_"),
        }

    async def handle_webhook(self, payload: bytes, signature: str) -> None:
        self._configure()
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise HTTPException(
                status_code=503, detail="Stripe webhook is not configured"
            )
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise HTTPException(
                status_code=400, detail="Invalid Stripe webhook"
            ) from exc
        if event["type"] != "checkout.session.completed":
            return
        session = event["data"]["object"]
        payment = await self.payments.get_by_provider_session_id(session["id"])
        if payment is None or payment.status == PaymentStatus.PAID.value:
            return
        if session.get("payment_status") != "paid":
            return
        if (
            session.get("amount_total") != payment.amount_cents
            or session.get("currency", "").upper() != payment.currency.upper()
        ):
            raise HTTPException(
                status_code=400, detail="Stripe payment amount mismatch"
            )
        payment.status = PaymentStatus.PAID.value
        await self.payments.update(payment)
        reservation = await self.reservations.get_by_id(payment.reservation_id)
        if reservation and reservation.status == ReservationStatus.PENDING.value:
            reservation.status = ReservationStatus.CONFIRMED.value
            reservation.hold_expires_at = None
            await self.reservations.update(reservation)

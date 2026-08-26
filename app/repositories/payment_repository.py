from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment


class PaymentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        payment: Payment,
    ) -> Payment:
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

    async def get_by_reservation_id(
        self,
        reservation_id: int,
    ) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.reservation_id == reservation_id)
        )

        return result.scalar_one_or_none()

    async def get_by_provider_session_id(self, session_id: str) -> Payment | None:
        result = await self.db.execute(
            select(Payment).where(Payment.provider_session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        payment: Payment,
    ) -> Payment:
        await self.db.commit()
        await self.db.refresh(payment)
        return payment

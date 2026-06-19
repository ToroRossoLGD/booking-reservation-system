from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reservation import ReservationStatus
from app.repositories.admin_repository import AdminRepository
from app.schemas.admin import AdminStatsRead


class AdminService:
    def __init__(self, db: AsyncSession):
        self.admin_repository = AdminRepository(db)

    async def get_stats(self) -> AdminStatsRead:
        reservations_by_status = (
            await self.admin_repository.count_reservations_by_status()
        )

        normalized_statuses = {
            status.value: reservations_by_status.get(status.value, 0)
            for status in ReservationStatus
        }

        return AdminStatsRead(
            total_users=await self.admin_repository.count_users(),
            total_venues=await self.admin_repository.count_venues(),
            total_resources=await self.admin_repository.count_resources(),
            total_reservations=await self.admin_repository.count_reservations(),
            reservations_by_status=normalized_statuses,
            total_payments=await self.admin_repository.count_payments(),
            total_revenue_cents=await self.admin_repository.get_total_revenue_cents(),
        )
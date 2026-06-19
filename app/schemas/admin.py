from pydantic import BaseModel


class AdminStatsRead(BaseModel):
    total_users: int
    total_venues: int
    total_resources: int
    total_reservations: int
    reservations_by_status: dict[str, int]
    total_payments: int
    total_revenue_cents: int
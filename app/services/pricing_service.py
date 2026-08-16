from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal


class PricingService:
    @staticmethod
    def calculate_amount_cents(
        hourly_rate_cents: int,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        duration_seconds = Decimal(str((end_time - start_time).total_seconds()))
        amount = Decimal(hourly_rate_cents) * duration_seconds / Decimal(3600)
        return max(1, int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

import csv
import io
from dataclasses import dataclass
from datetime import date
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.analytics import VenueAnalyticsRead
from app.services.analytics_service import AnalyticsService

AnalyticsReportType = Literal["daily", "resources", "reservations"]


@dataclass(frozen=True)
class AnalyticsCSVExport:
    filename: str
    content: str


class AnalyticsExportService:
    DANGEROUS_CELL_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

    def __init__(self, db: AsyncSession):
        self.analytics_service = AnalyticsService(db)

    async def export_csv(
        self,
        venue_id: int,
        start_date: date,
        end_date: date,
        report_type: AnalyticsReportType,
        current_user: User,
    ) -> AnalyticsCSVExport:
        venue, rows = await self.analytics_service.load_venue_report_data(
            venue_id=venue_id,
            start_date=start_date,
            end_date=end_date,
            current_user=current_user,
        )
        analytics = self.analytics_service._aggregate(venue, start_date, end_date, rows)

        if report_type == "daily":
            content = self._daily_csv(analytics)
        elif report_type == "resources":
            content = self._resources_csv(analytics)
        else:
            content = self._reservations_csv(rows)

        filename = (
            f"venue-{venue_id}-{report_type}-{start_date.isoformat()}-"
            f"{end_date.isoformat()}.csv"
        )
        return AnalyticsCSVExport(filename=filename, content=content)

    @classmethod
    def _safe_cell(cls, value):
        if value is None:
            return ""
        if not isinstance(value, str):
            return value
        if value.lstrip().startswith(cls.DANGEROUS_CELL_PREFIXES):
            return f"'{value}"
        return value

    @classmethod
    def _write_csv(cls, headers: list[str], rows: list[list]) -> str:
        output = io.StringIO(newline="")
        output.write("\ufeff")
        writer = csv.writer(output, lineterminator="\r\n")
        writer.writerow(headers)
        writer.writerows([[cls._safe_cell(value) for value in row] for row in rows])
        return output.getvalue()

    @staticmethod
    def _currencies(analytics: VenueAnalyticsRead) -> list[str]:
        currencies = set(analytics.revenue_by_currency)
        for day in analytics.daily:
            currencies.update(day.revenue_by_currency)
        for resource in analytics.resources:
            currencies.update(resource.revenue_by_currency)
        return sorted(currencies)

    @staticmethod
    def _revenue_headers(currencies: list[str]) -> list[str]:
        return [
            f"{metric}_{currency}"
            for currency in currencies
            for metric in (
                "gross_revenue_cents",
                "refunded_amount_cents",
                "net_revenue_cents",
            )
        ]

    @staticmethod
    def _revenue_cells(revenue_by_currency, currencies: list[str]) -> list[int]:
        cells = []
        for currency in currencies:
            revenue = revenue_by_currency.get(currency)
            cells.extend(
                [
                    revenue.gross_revenue_cents if revenue else 0,
                    revenue.refunded_amount_cents if revenue else 0,
                    revenue.net_revenue_cents if revenue else 0,
                ]
            )
        return cells

    @classmethod
    def _daily_csv(cls, analytics: VenueAnalyticsRead) -> str:
        currencies = cls._currencies(analytics)
        headers = [
            "date",
            "reservation_count",
            "booked_minutes",
            "booked_capacity_minutes",
            "cancelled_count",
            "no_show_count",
            *cls._revenue_headers(currencies),
        ]
        rows = [
            [
                day.date.isoformat(),
                day.reservation_count,
                day.booked_minutes,
                day.booked_capacity_minutes,
                day.cancelled_count,
                day.no_show_count,
                *cls._revenue_cells(day.revenue_by_currency, currencies),
            ]
            for day in analytics.daily
        ]
        return cls._write_csv(headers, rows)

    @classmethod
    def _resources_csv(cls, analytics: VenueAnalyticsRead) -> str:
        currencies = cls._currencies(analytics)
        statuses = sorted(analytics.reservations_by_status)
        headers = [
            "resource_id",
            "resource_name",
            "reservation_count",
            "booked_minutes",
            "booked_capacity_minutes",
            *[f"reservations_{status}" for status in statuses],
            *cls._revenue_headers(currencies),
        ]
        rows = [
            [
                resource.resource_id,
                resource.resource_name,
                resource.reservation_count,
                resource.booked_minutes,
                resource.booked_capacity_minutes,
                *[
                    resource.reservations_by_status.get(status, 0)
                    for status in statuses
                ],
                *cls._revenue_cells(resource.revenue_by_currency, currencies),
            ]
            for resource in analytics.resources
        ]
        return cls._write_csv(headers, rows)

    @classmethod
    def _reservations_csv(cls, rows) -> str:
        headers = [
            "reservation_id",
            "user_id",
            "resource_id",
            "resource_name",
            "start_time_utc",
            "end_time_utc",
            "status",
            "attendance_status",
            "party_size",
            "duration_minutes",
            "booked_capacity_minutes",
            "quoted_amount_cents",
            "quoted_currency",
            "promotion_code",
            "payment_status",
            "payment_provider",
            "payment_currency",
            "payment_amount_cents",
            "refunded_amount_cents",
            "net_payment_cents",
            "cancellation_fee_cents",
        ]
        csv_rows = []
        for reservation, resource, payment in rows:
            duration = max(
                0,
                int(
                    (reservation.end_time - reservation.start_time).total_seconds() / 60
                ),
            )
            payment_amount = payment.amount_cents if payment else None
            refunded_amount = payment.refunded_amount_cents if payment else None
            csv_rows.append(
                [
                    reservation.id,
                    reservation.user_id,
                    resource.id,
                    resource.name,
                    reservation.start_time.isoformat(),
                    reservation.end_time.isoformat(),
                    reservation.status,
                    reservation.attendance_status,
                    reservation.party_size,
                    duration,
                    duration * reservation.party_size,
                    reservation.quoted_amount_cents,
                    reservation.quoted_currency,
                    reservation.promotion_code,
                    payment.status if payment else None,
                    payment.provider if payment else None,
                    payment.currency if payment else None,
                    payment_amount,
                    refunded_amount,
                    payment_amount - refunded_amount if payment else None,
                    payment.cancellation_fee_cents if payment else None,
                ]
            )
        return cls._write_csv(headers, csv_rows)

from datetime import UTC, datetime, timedelta

from app.services.pricing_service import PricingService


def test_hourly_price_is_prorated_to_the_nearest_cent():
    start_time = datetime(2026, 8, 20, 10, tzinfo=UTC)

    amount = PricingService.calculate_amount_cents(
        hourly_rate_cents=1001,
        start_time=start_time,
        end_time=start_time + timedelta(minutes=90),
    )

    assert amount == 1502


def test_positive_duration_has_a_minimum_price_of_one_cent():
    start_time = datetime(2026, 8, 20, 10, tzinfo=UTC)

    amount = PricingService.calculate_amount_cents(
        hourly_rate_cents=1,
        start_time=start_time,
        end_time=start_time + timedelta(seconds=1),
    )

    assert amount == 1


def test_percentage_discount_is_rounded_to_nearest_cent():
    assert PricingService.calculate_discount_cents(1001, 15) == 150

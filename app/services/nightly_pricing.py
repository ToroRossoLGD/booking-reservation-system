from datetime import timedelta

from app.schemas.seasonal_rate import NightlyPrice


def nightly_prices(listing, check_in, check_out):
    """Price local calendar nights; checkout never consumes a night's rate."""
    rates = listing.seasonal_rates or []
    result = []
    for offset in range((check_out - check_in).days):
        day = check_in + timedelta(days=offset)
        price = listing.price_cents
        for rate in rates:
            if rate["start"] <= day.isoformat() < rate["end"]:
                price = rate["price_cents"]
                break
        result.append(NightlyPrice(date=day, price_cents=price))
    return result

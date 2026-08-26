import pytest
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.venue import VenueCreate


def test_stripe_live_key_is_rejected_by_default(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_live_accidental")
    monkeypatch.setattr(settings, "STRIPE_ALLOW_LIVE_MODE", False)

    with pytest.raises(ValueError, match="Live Stripe keys are disabled"):
        settings.validate_stripe_safety()


def test_stripe_test_key_passes_safety_guard(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_safe")
    monkeypatch.setattr(settings, "STRIPE_ALLOW_LIVE_MODE", False)

    settings.validate_stripe_safety()


def test_venue_coordinates_must_be_supplied_as_a_pair():
    with pytest.raises(ValidationError, match="provided together"):
        VenueCreate(name="Mapped venue", address="Main Street", latitude=44.8)


def test_venue_coordinates_accept_valid_pair():
    venue = VenueCreate(
        name="Mapped venue",
        address="Main Street",
        latitude=44.8125,
        longitude=20.4612,
    )

    assert venue.latitude == 44.8125
    assert venue.longitude == 20.4612

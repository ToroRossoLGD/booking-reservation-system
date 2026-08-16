from datetime import UTC, datetime, timedelta

from app.core.security import (
    create_access_token,
    create_check_in_token,
    decode_check_in_token,
)


def test_check_in_token_round_trip():
    token = create_check_in_token(
        reservation_id=42,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )

    assert decode_check_in_token(token) == 42


def test_access_token_cannot_be_used_as_check_in_pass():
    assert decode_check_in_token(create_access_token(subject=42)) is None


def test_expired_check_in_token_is_rejected():
    token = create_check_in_token(
        reservation_id=42,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    assert decode_check_in_token(token) is None

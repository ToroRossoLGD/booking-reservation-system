from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from jose.exceptions import JWTError
from passlib.context import CryptContext

from app.core.config import settings

password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_password, hashed_password)


def create_access_token(
    subject: str | int, expires_delta: timedelta | None = None
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_EXPIRE_MINUTES)

    expire = datetime.now(UTC) + expires_delta

    payload: dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_check_in_token(
    reservation_id: int,
    expires_at: datetime,
) -> str:
    return jwt.encode(
        {
            "sub": str(reservation_id),
            "type": "reservation_check_in",
            "exp": expires_at,
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_check_in_token(token: str) -> int | None:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None

    if payload.get("type") != "reservation_check_in":
        return None

    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None

import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    DEMO_MODE: bool = False
    DEMO_OWNER_PASSWORD: str = ""
    DEMO_GUEST_PASSWORD: str = ""
    APP_ENV: Literal["development", "test", "production"] = "development"
    APP_NAME: str
    FRONTEND_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    DATABASE_URL: str
    SQL_ECHO: bool = False

    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    MAX_ACTIVE_API_KEYS: int = 10

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    FRONTEND_URL: str = "http://localhost:5173"
    OAUTH_COOKIE_SECURE: bool = False

    S3_ENDPOINT_URL: str = ""
    S3_REGION: str = "us-east-1"
    S3_BUCKET: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_PUBLIC_BASE_URL: str = ""
    S3_PRESIGNED_URL_EXPIRE_SECONDS: int = 3600
    MEDIA_MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    PROPERTY_PHOTO_BUCKET: str = ""

    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_ALLOW_LIVE_MODE: bool = False

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM_EMAIL: str = "no-reply@booking.local"
    SMTP_FROM_NAME: str = "Booking Reservation System"

    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_EXPIRE_PENDING_INTERVAL_MINUTES: int = 5
    CELERY_NO_SHOW_INTERVAL_MINUTES: int = 5
    CELERY_REMINDER_INTERVAL_MINUTES: int = 5
    CELERY_ANALYTICS_REFRESH_HOUR_UTC: int = 2

    RESERVATION_EXPIRE_MINUTES: int = 15
    CHECK_IN_EARLY_MINUTES: int = 30
    NO_SHOW_GRACE_MINUTES: int = 15
    RESERVATION_FIRST_REMINDER_HOURS: int = 24
    RESERVATION_FINAL_REMINDER_HOURS: int = 2
    GUEST_INVITATION_EXPIRE_HOURS: int = 72
    RESERVATION_TRANSFER_EXPIRE_HOURS: int = 48
    MAX_ACTIVE_VENUE_WEBHOOKS: int = 10
    WEBHOOK_TIMEOUT_SECONDS: float = 10
    WEBHOOK_MAX_ATTEMPTS: int = 5
    WEBHOOK_RETRY_BASE_SECONDS: int = 60
    CELERY_WEBHOOK_INTERVAL_SECONDS: int = 30
    MAX_ACTIVE_CALENDAR_FEEDS: int = 10
    CALENDAR_FEED_PAST_DAYS: int = 30
    CALENDAR_FEED_FUTURE_DAYS: int = 365

    CACHE_TTL_SECONDS: int = 60

    FREE_CANCELLATION_HOURS: int = 24
    LATE_CANCELLATION_REFUND_PERCENT: int = 50

    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, hide_input_in_errors=True
    )

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.DEMO_MODE:
            database = make_url(self.DATABASE_URL)
            if (
                database.drivername != "postgresql+asyncpg"
                or not database.database
                or not database.database.endswith("_demo")
                or database.database != self.POSTGRES_DB
            ):
                raise ValueError(
                    "Demo requires a dedicated PostgreSQL database ending in _demo."
                )
        if self.APP_ENV != "production":
            return self

        def require_secret(name, value, minimum=16):
            normalized = "".join(c for c in value.lower() if c.isalnum())
            placeholders = (
                "changeme",
                "replaceme",
                "yourpassword",
                "yoursecret",
                "example",
                "placeholder",
                "postgres123",
                "password",
                "minioadmin",
                "smokeonly",
            )
            if (
                len(value.strip()) < minimum
                or len(set(value)) < 8
                or any(marker in normalized for marker in placeholders)
            ):
                raise ValueError(
                    f"Production configuration: {name} requires a generated secret."
                )

        require_secret("JWT_SECRET", self.JWT_SECRET, 32)
        require_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD)
        try:
            database = make_url(self.DATABASE_URL)
        except Exception:
            raise ValueError(
                "Production configuration: DATABASE_URL is invalid."
            ) from None
        if database.drivername != "postgresql+asyncpg" or not database.password:
            raise ValueError(
                "Production configuration: DATABASE_URL requires "
                "PostgreSQL credentials."
            )
        require_secret("DATABASE_URL password", database.password)
        if database.password != self.POSTGRES_PASSWORD:
            raise ValueError("Production configuration: database passwords must match.")
        if self.JWT_SECRET == self.POSTGRES_PASSWORD:
            raise ValueError(
                "Production configuration: JWT and database secrets must differ."
            )
        if self.SQL_ECHO:
            raise ValueError("Production configuration: SQL_ECHO must be disabled.")
        for public_name, secret_name in (
            ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"),
            ("S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY"),
        ):
            public, secret = getattr(self, public_name), getattr(self, secret_name)
            if bool(public.strip()) != bool(secret.strip()):
                raise ValueError(
                    f"Production configuration: configure both {public_name} "
                    f"and {secret_name}, or neither."
                )
            if secret:
                require_secret(secret_name, secret)
        for name in ("STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"):
            if value := getattr(self, name):
                require_secret(name, value)
        self.validate_stripe_safety()
        self.validate_production_origins()
        return self

    @property
    def google_login_enabled(self) -> bool:
        return not self.DEMO_MODE and bool(
            self.GOOGLE_CLIENT_ID.strip() and self.GOOGLE_CLIENT_SECRET.strip()
        )

    def validate_production_origins(self) -> None:
        def check_origin(value, name):
            try:
                parsed = urlsplit(value)
                valid = (
                    parsed.scheme == "https"
                    and parsed.hostname
                    and "." in parsed.hostname
                    and re.fullmatch(
                        r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"
                        r"(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+",
                        parsed.hostname,
                    )
                    and not parsed.hostname.endswith(
                        (".example", ".invalid", ".localhost")
                    )
                    and not parsed.username
                    and not parsed.password
                    and not parsed.path
                    and not parsed.query
                    and not parsed.fragment
                    and not any(c.isspace() for c in value)
                    and "*" not in value
                    and parsed.port != 0
                )
            except ValueError:
                valid = False
            if not valid:
                raise ValueError(
                    f"Production configuration: {name} requires an HTTPS origin "
                    "without credentials, path, query or fragment."
                )

        check_origin(self.FRONTEND_URL, "FRONTEND_URL")
        origins = [origin.strip() for origin in self.FRONTEND_ORIGINS.split(",")]
        for origin in origins:
            check_origin(origin, "FRONTEND_ORIGINS")
        if self.FRONTEND_URL not in origins:
            raise ValueError(
                "Production configuration: FRONTEND_ORIGINS must include FRONTEND_URL."
            )
        if self.google_login_enabled:
            if not self.OAUTH_COOKIE_SECURE:
                raise ValueError(
                    "Production configuration: Google login requires "
                    "OAUTH_COOKIE_SECURE."
                )
            if self.GOOGLE_REDIRECT_URI != (
                self.FRONTEND_URL + "/api/auth/google/callback"
            ):
                raise ValueError(
                    "Production configuration: GOOGLE_REDIRECT_URI must use "
                    "FRONTEND_URL followed by /api/auth/google/callback."
                )

    def validate_stripe_safety(self) -> None:
        if (
            self.STRIPE_SECRET_KEY.startswith("sk_live_")
            and not self.STRIPE_ALLOW_LIVE_MODE
        ):
            raise ValueError(
                "Live Stripe keys are disabled. Use an sk_test_ key or explicitly set "
                "STRIPE_ALLOW_LIVE_MODE=true."
            )


settings = Settings()

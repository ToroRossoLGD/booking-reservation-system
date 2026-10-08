import secrets

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings


def production(**overrides):
    password = secrets.token_hex(24)
    values = settings.model_dump()
    values.update(
        APP_ENV="production",
        JWT_SECRET=secrets.token_hex(32),
        POSTGRES_PASSWORD=password,
        DATABASE_URL=f"postgresql+asyncpg://bookica:{password}@postgres/bookica",
        SQL_ECHO=False,
        FRONTEND_URL="https://bookica.test",
        FRONTEND_ORIGINS="https://bookica.test",
        GOOGLE_CLIENT_ID="",
        GOOGLE_CLIENT_SECRET="",
        S3_ACCESS_KEY_ID="",
        S3_SECRET_ACCESS_KEY="",
        STRIPE_SECRET_KEY="",
        STRIPE_WEBHOOK_SECRET="",
    )
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_accepts_generated_secrets_and_disabled_integrations():
    assert production().APP_ENV == "production"


@pytest.mark.parametrize(
    "value",
    [
        "",
        "change-me",
        "a" * 64,
        "replace-me-" * 8,
        "your-secret-example-12345678901234567890",
    ],
)
def test_production_rejects_bad_jwt_without_disclosing_values(value):
    with pytest.raises(ValidationError) as error:
        production(JWT_SECRET=value)
    assert "JWT_SECRET requires a generated secret" in str(error.value)
    assert "input_value" not in str(error.value)
    if value:
        assert value not in str(error.value)


@pytest.mark.parametrize(
    "overrides,field",
    [
        ({"POSTGRES_PASSWORD": "postgres123"}, "POSTGRES_PASSWORD"),
        ({"DATABASE_URL": "not-a-url-private-value"}, "DATABASE_URL"),
        (
            {"DATABASE_URL": "postgresql+asyncpg://user:postgres123@postgres/db"},
            "DATABASE_URL password",
        ),
        ({"DATABASE_URL": "sqlite:///local.db"}, "DATABASE_URL"),
        ({"SQL_ECHO": True}, "SQL_ECHO"),
        ({"GOOGLE_CLIENT_ID": "configured"}, "GOOGLE_CLIENT_SECRET"),
        ({"S3_SECRET_ACCESS_KEY": "private-unpaired-value"}, "S3_ACCESS_KEY_ID"),
        ({"STRIPE_WEBHOOK_SECRET": "whsec_change-me"}, "STRIPE_WEBHOOK_SECRET"),
    ],
)
def test_production_rejects_unsafe_configuration(overrides, field):
    with pytest.raises(ValidationError, match=field) as error:
        production(**overrides)
    assert "input_value" not in str(error.value)


def test_database_passwords_must_match():
    with pytest.raises(ValidationError, match="passwords must match"):
        production(
            DATABASE_URL=f"postgresql+asyncpg://u:{secrets.token_hex(24)}@postgres/db"
        )


def test_url_encoded_password_is_compared_decoded():
    from urllib.parse import quote

    password = secrets.token_hex(24) + "@:/%"
    assert production(
        POSTGRES_PASSWORD=password,
        DATABASE_URL=f"postgresql+asyncpg://u:{quote(password, safe='')}@postgres/db",
    )


def test_production_rejects_reused_jwt_and_database_secret():
    password = secrets.token_hex(32)
    with pytest.raises(ValidationError, match="must differ"):
        production(
            JWT_SECRET=password,
            POSTGRES_PASSWORD=password,
            DATABASE_URL=f"postgresql+asyncpg://u:{password}@postgres/db",
        )


def test_production_rejects_unapproved_live_stripe_key():
    with pytest.raises(ValidationError, match="Live Stripe keys are disabled"):
        production(
            STRIPE_SECRET_KEY="sk_live_" + secrets.token_hex(24),
            STRIPE_ALLOW_LIVE_MODE=False,
        )


def test_development_keeps_existing_local_configuration():
    assert production(
        APP_ENV="development", JWT_SECRET="change-me", POSTGRES_PASSWORD="postgres123"
    )


def test_invalid_environment_is_not_silently_treated_as_development():
    with pytest.raises(ValidationError):
        production(APP_ENV="prodution")


@pytest.mark.parametrize(
    "origin",
    [
        "http://bookica.test",
        "https://bookica.test/",
        "https://bookica.test/app",
        "https://user:private@bookica.test",
        "https://bookica.test?x=1",
        "https://bookica.test#fragment",
        "https://bookica.your-domain.example",
        "*",
        "https://bookica.test:bad",
        "https://bookica.test:0",
        "",
    ],
)
def test_production_rejects_invalid_frontend_origins(origin):
    with pytest.raises(ValidationError, match="FRONTEND_URL"):
        production(FRONTEND_URL=origin)


@pytest.mark.parametrize(
    "origins",
    ["*", "http://bookica.test", "https://other.test", "https://bookica.test,"],
)
def test_production_rejects_invalid_or_mismatched_cors_origins(origins):
    with pytest.raises(ValidationError, match="FRONTEND_ORIGINS"):
        production(FRONTEND_ORIGINS=origins)


def test_production_accepts_explicit_additional_https_origins():
    assert production(FRONTEND_ORIGINS="https://bookica.test, https://other.test")


@pytest.mark.parametrize(
    "override,field",
    [
        ({"OAUTH_COOKIE_SECURE": False}, "OAUTH_COOKIE_SECURE"),
        (
            {"GOOGLE_REDIRECT_URI": "https://other.test/api/auth/google/callback"},
            "GOOGLE_REDIRECT_URI",
        ),
        (
            {"GOOGLE_REDIRECT_URI": "https://bookica.test/auth/google/callback"},
            "GOOGLE_REDIRECT_URI",
        ),
    ],
)
def test_google_requires_secure_cookies_and_exact_proxy_callback(override, field):
    values = dict(
        GOOGLE_CLIENT_ID="configured",
        GOOGLE_CLIENT_SECRET=secrets.token_hex(24),
        GOOGLE_REDIRECT_URI="https://bookica.test/api/auth/google/callback",
        OAUTH_COOKIE_SECURE=True,
    )
    values.update(override)
    with pytest.raises(ValidationError, match=field):
        production(**values)


def test_production_google_configuration_and_disabled_callback():
    assert production(
        GOOGLE_CLIENT_ID="configured",
        GOOGLE_CLIENT_SECRET=secrets.token_hex(24),
        GOOGLE_REDIRECT_URI="https://bookica.test/api/auth/google/callback",
        OAUTH_COOKIE_SECURE=True,
    ).google_login_enabled
    assert not production(GOOGLE_REDIRECT_URI="unused").google_login_enabled

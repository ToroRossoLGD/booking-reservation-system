from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    DATABASE_URL: str

    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = 0

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM_EMAIL: str = "no-reply@booking.local"
    SMTP_FROM_NAME: str = "Booking Reservation System"
    
    CACHE_TTL_SECONDS: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


settings = Settings()
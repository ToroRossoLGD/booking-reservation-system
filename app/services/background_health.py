"""Private operational probes for the single-scheduler deployment."""

from redis import Redis

from app.core.config import settings

HEARTBEAT_KEY = "bookica:ops:scheduler-heartbeat"
HEARTBEAT_TTL = 90


def broker_client():
    return Redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_connect_timeout=3,
        socket_timeout=3,
    )


def record_heartbeat():
    with broker_client() as client:
        client.set(HEARTBEAT_KEY, "ok", ex=HEARTBEAT_TTL)


def scheduler_healthy():
    with broker_client() as client:
        # A missing/expired key or one accidentally written without expiry fails.
        with client.pipeline() as pipeline:
            value, ttl = pipeline.get(HEARTBEAT_KEY).ttl(HEARTBEAT_KEY).execute()
        return value == b"ok" and 0 < ttl <= HEARTBEAT_TTL

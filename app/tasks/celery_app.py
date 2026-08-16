from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "booking_reservation_system",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.reservation_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "expire-pending-reservations-periodically": {
            "task": "expire_pending_reservations_task",
            "schedule": settings.CELERY_EXPIRE_PENDING_INTERVAL_MINUTES * 60,
        },
        "mark-reservation-no-shows-periodically": {
            "task": "mark_reservation_no_shows_task",
            "schedule": settings.CELERY_NO_SHOW_INTERVAL_MINUTES * 60,
        },
    },
)

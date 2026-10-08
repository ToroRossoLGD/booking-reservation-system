from app.services.background_health import record_heartbeat
from app.tasks.celery_app import celery_app


@celery_app.task(name="record_scheduler_heartbeat", ignore_result=True)
def record_scheduler_heartbeat():
    record_heartbeat()

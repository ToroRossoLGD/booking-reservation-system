from unittest.mock import MagicMock

import pytest

from app import runtime_health
from app.services import background_health
from app.tasks.celery_app import celery_app
from app.tasks.health_tasks import record_scheduler_heartbeat


@pytest.mark.parametrize(
    "value,ttl,healthy",
    [
        (b"ok", 90, True),
        (b"ok", 1, True),
        (None, -2, False),
        (b"ok", -1, False),
        (b"ok", 0, False),
        (b"ok", 91, False),
        (b"other", 30, False),
    ],
)
def test_scheduler_requires_valid_unexpired_heartbeat(monkeypatch, value, ttl, healthy):
    client = MagicMock()
    monkeypatch.setattr(background_health, "broker_client", lambda: client)
    pipeline = (
        client.__enter__.return_value.pipeline.return_value.__enter__.return_value
    )
    pipeline.get.return_value.ttl.return_value.execute.return_value = [value, ttl]
    assert background_health.scheduler_healthy() is healthy


def test_scheduled_task_records_expiring_marker_without_customer_data(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(background_health, "broker_client", lambda: client)
    record_scheduler_heartbeat.run()
    client.__enter__.return_value.set.assert_called_once_with(
        background_health.HEARTBEAT_KEY, "ok", ex=90
    )
    assert record_scheduler_heartbeat.ignore_result
    schedule = celery_app.conf.beat_schedule["scheduler-heartbeat"]
    assert schedule["task"] == record_scheduler_heartbeat.name
    assert schedule["schedule"] < background_health.HEARTBEAT_TTL
    assert schedule["options"]["expires"] == 60


@pytest.mark.parametrize(
    "replies,healthy",
    [
        (None, False),
        ({}, False),
        ({"celery@other": {"ok": "pong"}}, False),
        ({"celery@local": {"error": "unavailable"}}, False),
        ({"celery@local": {"ok": "pong"}}, True),
    ],
)
def test_worker_health_requires_this_container_reply(monkeypatch, replies, healthy):
    monkeypatch.setattr(runtime_health.socket, "gethostname", lambda: "local")
    inspect = MagicMock()
    inspect.return_value.ping.return_value = replies
    monkeypatch.setattr(celery_app.control, "inspect", inspect)
    assert runtime_health.worker_healthy() is healthy
    inspect.assert_called_once_with(destination=["celery@local"], timeout=3)


@pytest.mark.parametrize("component", ["scheduler", "worker"])
def test_operational_errors_fail_closed_without_logging_credentials(
    monkeypatch, capsys, component
):
    def fail():
        raise RuntimeError("redis://user:private-password@broker/1")

    monkeypatch.setattr(runtime_health, component + "_healthy", fail)
    assert runtime_health.run_check(component) == 1
    assert capsys.readouterr().out == f"{component}: unhealthy\n"

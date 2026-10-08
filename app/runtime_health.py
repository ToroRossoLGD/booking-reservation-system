"""Run inside the target container: python -m app.runtime_health worker|scheduler."""

import argparse
import socket

from app.services.background_health import scheduler_healthy
from app.tasks.celery_app import celery_app


def worker_healthy():
    destination = f"celery@{socket.gethostname()}"
    replies = celery_app.control.inspect(destination=[destination], timeout=3).ping()
    return bool(replies and replies.get(destination, {}).get("ok") == "pong")


def run_check(component):
    try:
        healthy = worker_healthy() if component == "worker" else scheduler_healthy()
    except Exception:
        # Broker errors may include connection strings. Keep Docker health logs safe.
        healthy = False
    print(f"{component}: {'healthy' if healthy else 'unhealthy'}")
    return 0 if healthy else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=["worker", "scheduler"])
    raise SystemExit(run_check(parser.parse_args().component))

import socket
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.routers.stay_blocks import router
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.property_rate_limit import policy_for
from app.db.session import get_db
from app.services import occupancy_url_service as module
from app.services.occupancy_import_service import parse_calendar, sanitized_calendar
from tests import test_stays
from tests.test_occupancy_import import calendar, event
from tests.test_property_rate_limit import request
from tests.test_stays import GUEST, OWNER

stay_service = test_stays.service


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setattr(settings, "OCCUPANCY_IMPORT_ALLOWED_HOSTS", "calendar.example")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "PROPERTY_RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(settings, "APP_ENV", "test")


@pytest.mark.parametrize(
    "url",
    [
        "http://calendar.example/a",
        "https://evil.example/a",
        "https://sub.calendar.example/a",
        "https://calendar.example.evil/a",
        "https://calendar.example:444/a",
        "https://user:secret@calendar.example/a",
        "https://calendar.example/a#secret",
        "https://calendar.example/a\nHost:other",
        "https://calendar.example\\@evil/a",
        "https://127.0.0.1/a",
        "https://[::1]/a",
        "file:///etc/passwd",
    ],
)
def test_url_validation(url):
    with pytest.raises(HTTPException) as error:
        module.validate_url(url)
    assert error.value.status_code == 400


def test_disabled_exact_hosts_and_budget(monkeypatch):
    assert module.validate_url("https://calendar.example:443/export?token=secret") == (
        "calendar.example",
        "/export?token=secret",
    )
    policy = policy_for(request("/owner/properties/1/occupancy-import/url"))
    assert (policy.account_limit, policy.ip_limit, policy.seconds) == (6, 30, 60)
    monkeypatch.setattr(settings, "OCCUPANCY_IMPORT_ALLOWED_HOSTS", "")
    with pytest.raises(HTTPException) as error:
        module.validate_url("https://calendar.example/a")
    assert error.value.status_code == 503


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "169.254.169.254",
        "100.64.0.1",
        "::1",
        "fd00::1",
        "fe80::1",
        "::ffff:127.0.0.1",
        "2002:7f00:1::",
        "224.0.0.1",
    ],
)
def test_rejects_mixed_dns_answers(monkeypatch, ip):
    monkeypatch.setattr(
        module.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)),
        ],
    )
    with pytest.raises(HTTPException):
        module.public_address("calendar.example")


def transport(monkeypatch, body=b"calendar", status=200, headers=None):
    address = (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
    resolve = MagicMock(return_value=[address])
    monkeypatch.setattr(module.socket, "getaddrinfo", resolve)
    raw = MagicMock()
    monkeypatch.setattr(module.socket, "socket", MagicMock(return_value=raw))
    context = MagicMock()
    monkeypatch.setattr(
        module.ssl, "create_default_context", MagicMock(return_value=context)
    )
    response = MagicMock(status=status)
    response.__enter__.return_value = response
    response.getheader.side_effect = lambda name, default=None: (headers or {}).get(
        name, default
    )
    response.read.return_value = body
    conn = MagicMock()
    conn.getresponse.return_value = response
    monkeypatch.setattr(
        module.http.client, "HTTPSConnection", MagicMock(return_value=conn)
    )
    return raw, context, conn, resolve


def test_pins_address_keeps_tls_hostname_and_sends_no_app_credentials(monkeypatch):
    raw, context, conn, resolve = transport(monkeypatch)
    assert module.download_calendar("calendar.example", "/feed?secret=x") == "calendar"
    resolve.assert_called_once()
    raw.connect.assert_called_once_with(("8.8.8.8", 443))
    context.wrap_socket.assert_called_once_with(raw, server_hostname="calendar.example")
    assert conn.request.call_args.args == ("GET", "/feed?secret=x")
    assert set(conn.request.call_args.kwargs["headers"]) == {
        "Accept",
        "Accept-Encoding",
        "Connection",
    }
    conn.close.assert_called_once()
    raw.close.assert_called_once()


@pytest.mark.parametrize(
    "status,headers,body",
    [
        (302, {"Location": "http://127.0.0.1/secret"}, b""),
        (200, {"Content-Length": "100001"}, b""),
        (200, {}, b"x" * 100001),
        (200, {"Content-Encoding": "gzip"}, b""),
        (200, {"Content-Length": "99"}, b"short"),
    ],
    ids=["redirect", "declared-size", "stream-size", "compression", "truncated"],
)
def test_rejects_unsafe_responses(monkeypatch, status, headers, body):
    _, _, conn, _ = transport(monkeypatch, body, status, headers)
    with pytest.raises(HTTPException):
        module.download_calendar("calendar.example", "/feed")
    assert conn.request.call_count == 1
    conn.close.assert_called_once()


def test_sanitized_snapshot_preserves_dates_and_skips_without_metadata():
    source = calendar(
        event(),
        event(9, 11, "STATUS:CANCELLED\r\n"),
        event(20, 22, "TRANSP:TRANSPARENT\r\n"),
    )
    clean = sanitized_calendar(source)
    assert parse_calendar(clean) == parse_calendar(source)
    assert "Private guest" not in clean and "DESCRIPTION" not in clean


@pytest.mark.asyncio
async def test_authorize_before_fetch_and_private_http_snapshot(
    stay_service, monkeypatch
):
    fetch = MagicMock(return_value=calendar(event()))
    monkeypatch.setattr(module, "download_calendar", fetch)
    service = module.OccupancyUrlService(stay_service.repository.db)
    for user in (GUEST, SimpleNamespace(id=99, role="owner")):
        with pytest.raises(HTTPException):
            await service.fetch(1, user, "https://calendar.example/a")
    fetch.assert_not_called()
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    with pytest.raises(HTTPException):
        await service.fetch(1, OWNER, "https://calendar.example/a")
    fetch.assert_not_called()
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: stay_service.repository.db
    app.dependency_overrides[get_current_user] = lambda: OWNER
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/owner/properties/1/occupancy-import/url",
            json={"url": "https://calendar.example/a?secret=private"},
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert "Private guest" not in response.text and "private" not in response.text
        assert parse_calendar(response.json()["content"])[0]
    fetch.side_effect = OSError("https://calendar.example/a?secret=private")
    with pytest.raises(HTTPException) as error:
        await service.fetch(1, OWNER, "https://calendar.example/a")
    assert error.value.status_code == 502 and "private" not in error.value.detail

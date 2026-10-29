"""One-shot, allowlisted HTTPS calendar retrieval with a pinned public address."""

import asyncio
import http.client
import ipaddress
import socket
import ssl
import threading
from urllib.parse import urlsplit

from fastapi import HTTPException

from app.core.config import settings
from app.services.occupancy_import_service import MAX_BYTES, sanitized_calendar
from app.services.stay_block_service import StayBlockService


def validate_url(url):
    allowed = {
        host.strip().lower()
        for host in settings.OCCUPANCY_IMPORT_ALLOWED_HOSTS.split(",")
        if host.strip()
    }
    if not allowed:
        raise HTTPException(503, "Calendar URL import is not configured")
    try:
        if (
            not url.isascii()
            or any(ord(char) <= 32 or ord(char) == 127 for char in url)
            or "\\" in url
        ):
            raise ValueError
        parsed = urlsplit(url)
        host = parsed.hostname
        if (
            parsed.scheme != "https"
            or not host
            or host not in allowed
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.fragment
        ):
            raise ValueError
        # Even public literal IPs are not supported as configured providers.
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        return host, (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
    except ValueError:
        raise HTTPException(
            400, "Use an approved HTTPS calendar host on port 443"
        ) from None


def public_address(host):
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses:
        raise OSError("No addresses")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if (
            not ip.is_global
            or ip.is_multicast
            or ip.is_reserved
            or getattr(ip, "ipv4_mapped", None)
            or getattr(ip, "sixtofour", None)
            or getattr(ip, "teredo", None)
        ):
            raise HTTPException(400, "Calendar host must resolve to public addresses")
    return addresses[0]


def download_calendar(host, target):
    address = public_address(host)
    raw = socket.socket(address[0], address[1], address[2])
    conn = http.client.HTTPSConnection(host, timeout=5)
    transport = [raw]

    def abort():
        try:
            transport[0].shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    # Bound slow response headers/body as well as ordinary socket inactivity.
    timer = threading.Timer(15, abort)
    timer.daemon = True
    timer.start()
    try:
        raw.settimeout(5)
        raw.connect(address[4])  # No second DNS lookup, including on HTTPS connect.
        context = ssl.create_default_context()
        context.set_alpn_protocols(["http/1.1"])
        conn.sock = context.wrap_socket(raw, server_hostname=host)
        transport[0] = conn.sock
        conn.request(
            "GET",
            target,
            headers={
                "Accept": "text/calendar",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        with conn.getresponse() as response:
            # Never follow redirects or send app cookies/Authorization to providers.
            if response.status != 200:
                raise HTTPException(502, "Calendar provider did not return a calendar")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise HTTPException(400, "Compressed calendars are not supported")
            length = response.getheader("Content-Length")
            if length is not None and (not length.isdigit() or int(length) > MAX_BYTES):
                raise HTTPException(400, "Calendar exceeds the 100 KB limit")
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise HTTPException(400, "Calendar exceeds the 100 KB limit")
            if length is not None and len(body) != int(length):
                raise HTTPException(502, "Incomplete calendar response")
            return body.decode("utf-8-sig")
    finally:
        timer.cancel()
        conn.close()
        raw.close()


class OccupancyUrlService(StayBlockService):
    async def fetch(self, property_id, user, url):
        listing = await self.authorize(property_id, user)
        if settings.DEMO_MODE:
            raise HTTPException(403, "Calendar URL import is disabled in demo mode")
        if listing.offer_type != "short_stay":
            raise HTTPException(400, "Only short stays support calendar import")
        host, target = validate_url(url)
        try:
            content = await asyncio.wait_for(
                asyncio.to_thread(download_calendar, host, target), timeout=20
            )
        except (
            OSError,
            http.client.HTTPException,
            UnicodeError,
            ValueError,
            TimeoutError,
        ):
            # Do not expose provider URLs (often bearer secrets) in errors/logs.
            raise HTTPException(502, "Calendar could not be downloaded") from None
        return {"content": sanitized_calendar(content)}

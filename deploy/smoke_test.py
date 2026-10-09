"""Real-stack smoke check; use only with the isolated CI/smoke database."""

import argparse
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def write_env(path, demo=False):
    password = secrets.token_hex(24)
    database = "bookica_demo" if demo else "bookica"
    Path(path).write_text(
        "APP_NAME=Bookica smoke\nPOSTGRES_USER=bookica\n"
        f"POSTGRES_PASSWORD={password}\nPOSTGRES_DB={database}\n"
        f"DATABASE_URL=postgresql+asyncpg://bookica:{password}@postgres:5432/{database}\n"
        f"JWT_SECRET={secrets.token_hex(32)}\nJWT_ALGORITHM=HS256\n"
        "JWT_EXPIRE_MINUTES=60\nFRONTEND_URL=https://bookica.test\n"
        "FRONTEND_ORIGINS=https://bookica.test\nOAUTH_COOKIE_SECURE=true\n"
        f"GOOGLE_CLIENT_ID=smoke-only\nGOOGLE_CLIENT_SECRET={secrets.token_hex(24)}\n"
        "GOOGLE_REDIRECT_URI=https://bookica.test/api/auth/google/callback\n"
        "BOOKICA_HTTP_PORT=18080\nSMTP_MODE=disabled\n",
        encoding="utf-8",
    )
    if demo:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(
                f"DEMO_MODE=true\nDEMO_OWNER_PASSWORD={secrets.token_hex(24)}\n"
                f"DEMO_GUEST_PASSWORD={secrets.token_hex(24)}\n"
            )


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def smoke(base, expect_existing=False):
    opener = urllib.request.build_opener(NoRedirect)

    def request(path, data=None, headers=None):
        req = urllib.request.Request(base + path, data=data, headers=headers or {})
        try:
            response = opener.open(req, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    assert request("/healthz")[0] == 200
    status, headers, body = request("/api/auth/providers")
    assert status == 200 and json.loads(body) == {"google": True}
    assert headers["Cache-Control"] == "no-store"
    status, _, body = request("/api/ready")
    assert status == 200 and json.loads(body)["database"] == "available"
    status, headers, body = request("/properties/123")
    assert status == 200 and "text/html" in headers["Content-Type"]
    assert "no-cache" in headers["Cache-Control"]
    asset = re.search(rb'src="(/assets/[^\"]+\.js)"', body).group(1).decode()
    status, headers, _ = request(asset)
    assert status == 200 and "immutable" in headers["Cache-Control"]
    assert request("/assets/missing.js")[0] == 404
    status, headers, _ = request("/api/does-not-exist")
    assert status == 404 and "application/json" in headers["Content-Type"]
    status, _, body = request("/api/properties?limit=1")
    assert status == 200 and isinstance(json.loads(body)["items"], list)
    status, headers, _ = request("/api/auth/google/login")
    assert status == 302
    cookie = headers["Set-Cookie"]
    assert "Path=/api/auth/google" in cookie and "Secure" in cookie
    payload = {"email": "smoke@example.com", "password": "Smoke-password-only-42"}
    headers = {"Content-Type": "application/json"}
    status, _, _ = request(
        "/api/auth/register", json.dumps({**payload, "role": "admin"}).encode(), headers
    )
    assert status == 422
    status, _, _ = request("/api/auth/register", json.dumps(payload).encode(), headers)
    assert status == 409 if expect_existing else status in (201, 409)
    status, _, body = request(
        "/api/auth/login",
        urllib.parse.urlencode(
            {"username": payload["email"], "password": payload["password"]}
        ).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert status == 200
    status, _, body = request(
        "/api/auth/me",
        headers={"Authorization": "Bearer " + json.loads(body)["access_token"]},
    )
    assert status == 200 and json.loads(body)["role"] == "customer"
    print("Production-profile smoke checks passed (real API/PostgreSQL).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-env")
    parser.add_argument("--base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--expect-existing", action="store_true")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.write_env:
        write_env(args.write_env, args.demo)
    else:
        smoke(args.base_url, args.expect_existing)

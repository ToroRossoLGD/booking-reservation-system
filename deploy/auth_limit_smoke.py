"""Auth limiter acceptance against the disposable CI production stack only."""

import argparse
import json
import urllib.error
import urllib.request


def post(index):
    request = urllib.request.Request(
        "http://127.0.0.1:18080/api/auth/password-reset/request",
        data=b"{}",  # Invalid input: never email or look up a real account.
        headers={
            "Content-Type": "application/json",
            "Origin": "https://bookica.test",
            "X-Forwarded-For": f"198.51.100.{index + 1}",
            "X-Real-IP": f"203.0.113.{index + 1}",
        },
    )
    try:
        response = urllib.request.urlopen(request, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, json.load(response)


def main(mode):
    if mode == "exhaust":
        for index in range(5):
            assert post(index)[0] == 422
    status, headers, _ = post(42)
    assert status == (503 if mode == "unavailable" else 429)
    assert int(headers["Retry-After"]) > 0
    assert headers["Cache-Control"] == "no-store"
    assert headers["Access-Control-Allow-Origin"] == "https://bookica.test"
    assert "Retry-After" in headers["Access-Control-Expose-Headers"]
    assert headers["X-Request-ID"]
    with urllib.request.urlopen(
        "http://127.0.0.1:18080/api/health", timeout=10
    ) as response:
        assert response.status == 200
    print(f"Auth limit {mode} check passed; spoofed headers did not bypass the budget.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["exhaust", "persisted", "unavailable"])
    main(parser.parse_args().mode)

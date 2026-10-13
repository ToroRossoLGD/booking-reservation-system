"""Legacy integration/support/reservation acceptance; disposable CI stack only."""

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request


def request(
    path, method="POST", body=b"{}", token=None, content_type="application/json"
):
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        "http://127.0.0.1:18080/api" + path,
        data=body,
        method=method,
        headers=headers,
    )
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, json.load(response)


def main(mode):
    if mode == "unavailable":
        status, headers, _ = request("/auth/api-keys")
        assert status == 503 and headers["Retry-After"] == "30"
        status, headers, _ = request("/support/tickets")
        assert status == 503 and headers["Retry-After"] == "30"
        for method, path in [
            ("POST", "/reservations"),
            ("POST", "/reservations/recurring"),
            ("PATCH", "/reservations/99999999/reschedule"),
        ]:
            status, headers, _ = request(path, method=method)
            assert status == 503 and headers["Retry-After"] == "30"
        return
    status, _, data = request(
        "/auth/login",
        body=urllib.parse.urlencode(
            {"username": "smoke@example.com", "password": "Smoke-password-only-42"}
        ).encode(),
        content_type="application/x-www-form-urlencoded",
    )
    assert status == 200
    token = data["access_token"]
    if mode == "exhaust":
        # Invalid bodies consume admission budgets without creating bookings.
        for index in range(10):
            method, path = (
                ("POST", "/reservations")
                if index % 2 == 0
                else ("PATCH", f"/reservations/{index}/reschedule")
            )
            assert request(path, method=method, token=token)[0] == 422
        for _ in range(2):
            assert request("/reservations/recurring", token=token)[0] == 422
        for _ in range(5):
            assert request("/support/tickets", token=token)[0] == 422
        for index in range(30):
            assert (
                request(f"/support/tickets/{index + 1}/messages", token=token)[0] == 422
            )
        assert request("/support/tickets/999/messages", token=token)[0] == 429
        for _ in range(5):
            assert request("/auth/api-keys", token=token)[0] == 422
        for index in range(10):
            assert request(f"/venues/{index + 1}/webhooks", token=token)[0] == 422
            # Nonexistent objects: never enqueue actual deliveries.
            assert (
                request(
                    f"/venues/{99000000 + index}/webhooks/deliveries/1/retry",
                    token=token,
                )[0]
                == 404
            )
        assert (
            request("/venues/99999999/webhooks/deliveries/999/retry", token=token)[0]
            == 429
        )
    for method, path in [
        ("POST", "/reservations"),
        ("POST", "/reservations/recurring"),
        ("PATCH", "/reservations/99999999/reschedule"),
        ("POST", "/auth/api-keys"),
        ("PUT", "/venues/999/webhooks/999"),
    ]:
        status, headers, _ = request(path, method=method, token=token)
        assert status == 429
        assert int(headers["Retry-After"]) > 0
        assert headers["Cache-Control"] == "no-store"
        assert headers["X-Request-ID"]
    assert request("/auth/api-keys", method="GET", body=None, token=token)[0] == 200
    assert request("/reservations/my", method="GET", body=None, token=token)[0] == 200
    assert (
        request(
            "/reservations/99999999/cancel", method="PATCH", body=None, token=token
        )[0]
        == 404
    )
    assert (
        request("/auth/api-keys/99999999", method="DELETE", body=None, token=token)[0]
        == 404
    )
    assert (
        request("/venues/99999999/webhooks/1", method="DELETE", body=None, token=token)[
            0
        ]
        == 404
    )
    status, headers, _ = request("/support/tickets", token=token)
    assert status == 429 and int(headers["Retry-After"]) > 0
    assert (
        request("/support/tickets/my", method="GET", body=None, token=token)[0] == 200
    )
    assert (
        request(
            "/support/tickets/99999999/close", method="PATCH", body=None, token=token
        )[0]
        == 404
    )
    print(f"Legacy write budgets {mode}: shared limits and emergency actions passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["exhaust", "persisted", "unavailable"])
    main(parser.parse_args().mode)

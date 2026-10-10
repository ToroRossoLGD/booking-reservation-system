"""Property write-limit acceptance; disposable CI production stack only."""

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request


def request(path, body, headers=None):
    req = urllib.request.Request(
        "http://127.0.0.1:18080/api" + path,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, json.load(response)


def main(mode):
    if mode == "unavailable":
        status, headers, _ = request("/properties/1/reports", b"{}")
        assert status == 503 and headers["Retry-After"] == "30"
        print("Property writes rejected while limiter storage is unavailable.")
        return
    status, _, body = request(
        "/auth/login",
        urllib.parse.urlencode(
            {
                "username": "smoke@example.com",
                "password": "Smoke-password-only-42",
            }
        ).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert status == 200
    headers = {
        "Authorization": "Bearer " + body["access_token"],
        "Origin": "https://bookica.test",
    }
    if mode == "exhaust":
        # Invalid bodies: exercise account dependencies without creating reports.
        for index in range(5):
            assert request(f"/properties/{index + 1}/reports", b"{}", headers)[0] == 422
        # Anonymous attempts exercise IP protection before authentication.
        for index in range(60):
            assert (
                request(
                    f"/owner/properties/{index + 1}/photos",
                    b"{}",
                    {
                        "X-Forwarded-For": f"198.51.100.{index + 1}",
                    },
                )[0]
                == 401
            )
    for path, auth in [
        ("/properties/999/reports", headers),
        ("/owner/properties/999/photos", {}),
    ]:
        status, response_headers, _ = request(path, b"{}", auth)
        assert status == 429
        assert int(response_headers["Retry-After"]) > 0
        assert response_headers["X-Request-ID"]
    print(f"Property account/IP limits {mode}; changing listings did not bypass them.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["exhaust", "persisted", "unavailable"])
    main(parser.parse_args().mode)

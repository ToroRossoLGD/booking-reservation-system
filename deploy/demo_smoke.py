"""Disposable CI demo acceptance; never point at a customer database."""

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def smoke(after_reset=False):
    values = dict(
        line.split("=", 1)
        for line in Path(".env.production").read_text().splitlines()
        if "=" in line
    )
    base = "http://127.0.0.1:18080/api"

    def request(path, data=None, token=None, content_type="application/json"):
        headers = {"Content-Type": content_type}
        if token:
            headers["Authorization"] = "Bearer " + token
        try:
            response = urllib.request.urlopen(
                urllib.request.Request(base + path, data=data, headers=headers),
                timeout=15,
            )
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    assert json.loads(request("/runtime-config")[1]) == {"demo": True}
    assert json.loads(request("/auth/providers")[1]) == {"google": False}
    assert request("/auth/google/login")[0] == 503
    assert (
        request(
            "/auth/register",
            json.dumps(
                {"email": "new@example.com", "password": "Demo-only-pass-42"}
            ).encode(),
        )[0]
        == 403
    )
    tokens = {}
    users = {}
    for role, email, field in (
        ("owner", "owner@example.com", "DEMO_OWNER_PASSWORD"),
        ("customer", "guest@example.com", "DEMO_GUEST_PASSWORD"),
    ):
        status, body, _ = request(
            "/auth/login",
            urllib.parse.urlencode(
                {"username": email, "password": values[field]}
            ).encode(),
            content_type="application/x-www-form-urlencoded",
        )
        assert status == 200
        tokens[role] = json.loads(body)["access_token"]
        user = json.loads(request("/auth/me", token=tokens[role])[1])
        assert user["role"] == role
        users[role] = user["id"]
    listings = json.loads(request("/properties?limit=10")[1])["items"]
    assert len(listings) == 3
    assert {item["offer_type"] for item in listings} == {
        "short_stay",
        "long_term",
        "sale",
    }
    for listing in listings:
        photos = json.loads(
            request(f"/owner/properties/{listing['id']}/photos", token=tokens["owner"])[
                1
            ]
        )
        assert len(photos) == 1
        status, content, headers = request(
            f"/properties/{listing['id']}/photos/{photos[0]['id']}/image"
        )
        assert status == 200 and content.startswith(b"<svg")
        assert "image/svg+xml" in headers["Content-Type"]
    assert (
        request(
            f"/owner/properties/{listings[0]['id']}/photos",
            b"blocked",
            tokens["owner"],
            "multipart/form-data; boundary=test",
        )[0]
        == 403
    )
    state_path = Path(".demo-ci-state.json")
    if after_reset:
        old = json.loads(state_path.read_text())
        assert all(users[role] > old["users"][role] for role in users)
        assert request("/auth/me", token=old["token"])[0] == 401
        state_path.unlink()
    else:
        state_path.write_text(json.dumps({"users": users, "token": tokens["customer"]}))
    print("Demo accounts, listings, local illustrations and isolation checks passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-reset", action="store_true")
    smoke(parser.parse_args().after_reset)

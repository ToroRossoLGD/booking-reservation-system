"""CI-only canary checks for build context and image layers."""

import argparse
import json
import secrets
import subprocess
import tempfile
from pathlib import Path

CANARY_FILES = (
    ".env.build-canary",
    "frontend/.env.production.local",
    ".tools/build-canary.txt",
    ".aws/build-canary",
    "frontend/.ssh/build-canary",
    "deploy/build-canary.key",
    "deploy/credentials.json",
)


def contains_secret(stream, needles, chunk_size=1024 * 1024):
    overlap = max(map(len, needles)) - 1
    tail = b""
    while chunk := stream.read(chunk_size):
        data = tail + chunk
        if any(needle in data for needle in needles):
            return True
        tail = data[-overlap:] if overlap else b""
    return False


def prepare(path):
    marker = "bookica-build-canary-" + secrets.token_hex(32)
    for name in CANARY_FILES:
        target = Path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Do not overwrite an operator's files; this helper is for a fresh CI checkout.
        with target.open("x", encoding="utf-8") as handle:
            handle.write(marker)
    Path(path).write_text(marker, encoding="utf-8")


def verify(marker_path, env_path, images):
    values = [Path(marker_path).read_text(encoding="utf-8").strip()]
    sensitive = {
        "JWT_SECRET",
        "POSTGRES_PASSWORD",
        "GOOGLE_CLIENT_SECRET",
        "DEMO_OWNER_PASSWORD",
        "DEMO_GUEST_PASSWORD",
        "SMTP_PASSWORD",
    }
    for line in Path(env_path).read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key in sensitive and value:
            values.append(value)
    needles = [value.encode() for value in values]
    for image in images:
        # Docker save includes configuration/history and every uncompressed layer,
        # including files deleted in subsequent layers. No extraction is performed.
        with tempfile.TemporaryDirectory(prefix="bookica-image-check-") as directory:
            archive = Path(directory) / "image.tar"
            subprocess.run(
                ["docker", "image", "save", "-o", str(archive), image], check=True
            )
            with archive.open("rb") as handle:
                if contains_secret(handle, needles):
                    raise SystemExit(
                        "Build isolation failed: secret/canary in image archive."
                    )
        config = subprocess.check_output(["docker", "image", "inspect", image])
        if any(needle in config for needle in needles):
            raise SystemExit(
                "Build isolation failed: image metadata contains a secret/canary."
            )
        if not json.loads(config):
            raise SystemExit("Image inspection returned no configuration.")
    print("Passed: no injected secrets in build context, layers or frontend build.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--marker", required=True)
    parser.add_argument("--env-file", default=".env.production")
    parser.add_argument("images", nargs="*")
    args = parser.parse_args()
    if args.prepare:
        prepare(args.marker)
    else:
        if not args.images:
            parser.error("provide images to verify")
        verify(args.marker, args.env_file, args.images)

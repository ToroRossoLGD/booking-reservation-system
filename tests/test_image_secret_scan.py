from io import BytesIO

from deploy.check_image_secrets import contains_secret


def test_scanner_detects_a_secret_crossing_read_boundaries():
    assert contains_secret(
        BytesIO(b"1234567private-secret-end"), [b"private-secret"], chunk_size=8
    )


def test_scanner_accepts_content_without_secret():
    assert not contains_secret(
        BytesIO(b"public-frontend-code"), [b"private-secret"], chunk_size=3
    )

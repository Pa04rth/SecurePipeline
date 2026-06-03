# tests/security_headers_test.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

EXPECTED_HEADERS = {
    "Cache-Control": "no-store",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


@pytest.mark.parametrize(
    "path,expected_status",
    [
        ("/health", 200),
        ("/does-not-exist", 404),  # the case ZAP actually flagged
    ],
)
def test_security_headers_present(path, expected_status):
    response = client.get(path)
    assert response.status_code == expected_status
    for header, expected_value in EXPECTED_HEADERS.items():
        assert (
            response.headers.get(header) == expected_value
        ), f"Missing or wrong {header} on {path}: got {response.headers.get(header)!r}"

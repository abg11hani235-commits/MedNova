"""Unit tests for the health check endpoint."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health_check() -> None:
    """Assert that GET /health returns status 200 and {'status': 'ok'}."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

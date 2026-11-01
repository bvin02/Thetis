from fastapi.testclient import TestClient

from app.main import app


def test_health_is_ok():
    assert TestClient(app).get("/api/health").json() == {"ok": True}

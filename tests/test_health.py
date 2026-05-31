import os

os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["DISABLE_NOTIFICATIONS"] = "true"

from fastapi.testclient import TestClient

from main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "schedule-reminder"}

import os

from fastapi.testclient import TestClient

os.environ["ENABLE_BOT"] = "false"
os.environ["DISABLE_TELEGRAM_SEND"] = "true"
os.environ["BACKEND_MODE"] = "mock"

from app.main import app  # noqa: E402


def test_health_without_telegram_network_calls() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "schedule-reminder"
    assert response.json()["role"] == "telegram-adapter"
    assert response.json()["backend_mode"] == "mock"

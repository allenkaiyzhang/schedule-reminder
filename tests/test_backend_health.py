import os

from fastapi.testclient import TestClient


def test_health_ok_when_ops_core_unavailable() -> None:
    os.environ["ENABLE_BOT"] = "false"
    os.environ["DISABLE_TELEGRAM_SEND"] = "true"
    os.environ["BACKEND_MODE"] = "fallback"
    os.environ["OPS_CORE_BASE_URL"] = "http://127.0.0.1:9"

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["backend_mode"] == "fallback"


def test_backend_health_degraded_when_ops_core_unavailable() -> None:
    os.environ["ENABLE_BOT"] = "false"
    os.environ["DISABLE_TELEGRAM_SEND"] = "true"
    os.environ["BACKEND_MODE"] = "fallback"
    os.environ["OPS_CORE_BASE_URL"] = "http://127.0.0.1:9"

    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health/backend")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert "OPS_CORE_TOKEN" not in response.text

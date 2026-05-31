import os
import asyncio

import httpx

from app.backend import UiResponse, build_backend_client
from app.backend.mock_client import MockBackendClient
from app.backend.resilient_client import ResilientBackendClient
from app.config import get_settings
from app.renderer import render_markup, render_text


def _settings(mode: str):
    os.environ["BACKEND_MODE"] = mode
    os.environ["OPS_CORE_BASE_URL"] = "http://127.0.0.1:9"
    return get_settings()


def test_backend_mode_selection() -> None:
    assert build_backend_client(_settings("mock")).__class__.__name__ == "MockBackendClient"
    assert build_backend_client(_settings("fallback")).__class__.__name__ == "ResilientBackendClient"
    assert build_backend_client(_settings("ops")).__class__.__name__ == "OpsBackendClient"


def test_mock_mode_never_calls_ops_core(monkeypatch) -> None:
    async def fail_request(*args, **kwargs):
        raise AssertionError("mock mode must not call ops-core")

    monkeypatch.setattr(httpx.AsyncClient, "post", fail_request)
    client = MockBackendClient(_settings("mock"))
    response = asyncio.run(client.handle("reminder:create", {"text": "in 10m test"}))
    assert response.degraded is True
    assert response.success is False
    assert "No successful business action" in response.body


def test_fallback_uses_mock_after_ops_error() -> None:
    client = ResilientBackendClient(_settings("fallback"))
    response = asyncio.run(client.handle("reminder:create", {"text": "in 10m test"}))
    assert response.source == "mock"
    assert response.degraded is True
    assert response.success is False
    assert "ops-core unavailable" in response.title


def test_mock_response_contains_visible_banner() -> None:
    client = MockBackendClient(_settings("mock"))
    response = asyncio.run(client.handle("mock:home", {}))
    assert response.banner
    assert "MOCK MODE" in response.banner


def test_renderer_handles_mock_like_live_response() -> None:
    response = UiResponse(
        title="Live",
        body="Body",
        buttons=[],
        source="ops",
    )
    mock = UiResponse(
        title="Mock",
        body="Body",
        buttons=[],
        banner="MOCK MODE",
        source="mock",
        degraded=True,
    )
    assert "Live" in render_text(response)
    assert "MOCK MODE" in render_text(mock)
    assert render_markup(response) is None

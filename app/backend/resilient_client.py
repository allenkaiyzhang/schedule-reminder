from __future__ import annotations

from typing import Any

from app.backend.base import BackendHealth, BackendUnavailable, UiResponse
from app.backend.mock_client import MockBackendClient
from app.backend.ops_client import OpsBackendClient
from app.config import Settings


class ResilientBackendClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ops = OpsBackendClient(settings)
        self.mock = MockBackendClient(settings)
        self.last_error: str | None = None

    async def handle(self, action: str, payload: dict[str, Any]) -> UiResponse:
        try:
            return await self.ops.handle(action, payload)
        except BackendUnavailable as exc:
            self.last_error = str(exc)
            return await MockBackendClient(
                self.settings,
                reason="ops-core unavailable",
                last_success=False,
                last_error=str(exc),
            ).handle(action, payload)

    async def health(self) -> BackendHealth:
        health = await self.ops.health()
        self.last_error = health.last_error
        return health


def build_backend_client(settings: Settings):
    mode = settings.backend_mode
    if mode == "ops":
        return OpsBackendClient(settings)
    if mode == "mock":
        return MockBackendClient(settings)
    if mode == "fallback":
        return ResilientBackendClient(settings)
    raise ValueError(f"Unsupported backend mode: {mode}")

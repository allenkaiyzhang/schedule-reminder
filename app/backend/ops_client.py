from __future__ import annotations

from typing import Any

import httpx

from app.backend.base import BackendHealth, BackendUnavailable, UiButton, UiResponse
from app.config import Settings


class OpsBackendClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.last_success = False
        self.last_error: str | None = None

    async def handle(self, action: str, payload: dict[str, Any]) -> UiResponse:
        url = f"{self.settings.ops_core_base_url}{self.settings.backend_interaction_path}"
        headers = self._headers()
        body = {"action": action, "payload": payload}
        try:
            async with httpx.AsyncClient(timeout=self.settings.backend_timeout_seconds) as client:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            self.last_success = False
            self.last_error = str(exc)
            raise BackendUnavailable(str(exc)) from exc
        self.last_success = True
        self.last_error = None
        return _parse_ui_response(data)

    async def health(self) -> BackendHealth:
        url = f"{self.settings.ops_core_base_url}{self.settings.backend_health_path}"
        try:
            async with httpx.AsyncClient(timeout=self.settings.backend_timeout_seconds) as client:
                response = await client.get(url, headers=self._headers())
                response.raise_for_status()
            self.last_success = True
            self.last_error = None
            return BackendHealth("ok", self.settings.backend_mode, self.settings.ops_core_base_url, True)
        except Exception as exc:
            self.last_success = False
            self.last_error = str(exc)
            return BackendHealth(
                "degraded",
                self.settings.backend_mode,
                self.settings.ops_core_base_url,
                False,
                str(exc),
            )

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.settings.ops_core_token:
            headers["Authorization"] = f"Bearer {self.settings.ops_core_token}"
        return headers


def _parse_ui_response(data: dict[str, Any]) -> UiResponse:
    buttons = [
        UiButton(str(item.get("text", "")), str(item.get("action", "")))
        for item in data.get("buttons", [])
        if isinstance(item, dict)
    ]
    return UiResponse(
        title=str(data.get("title", "Response")),
        body=str(data.get("body", "")),
        buttons=buttons,
        banner=data.get("banner"),
        source=str(data.get("source", "ops")),
        success=bool(data.get("success", False)),
        degraded=bool(data.get("degraded", False)),
    )

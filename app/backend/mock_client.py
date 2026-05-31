from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.backend.base import BackendHealth, UiButton, UiResponse
from app.config import Settings


class MockBackendClient:
    def __init__(
        self,
        settings: Settings,
        *,
        reason: str | None = None,
        last_success: bool = False,
        last_error: str | None = None,
    ):
        self.settings = settings
        self.reason = reason
        self.last_success = last_success
        self.last_error = last_error or reason

    async def handle(self, action: str, payload: dict[str, Any]) -> UiResponse:
        if action in {"nav:home", "mock:home"}:
            return self._home()
        if action == "system:adapter_status":
            return self._status()
        if action.startswith("mock:"):
            return self._mock_screen(action)
        return self._business_unavailable(action, payload)

    async def health(self) -> BackendHealth:
        return BackendHealth(
            status="degraded" if self.reason else "ok",
            mode=self.settings.backend_mode,
            ops_core_base_url=self.settings.ops_core_base_url,
            last_success=self.last_success,
            last_error=self.last_error,
        )

    def _home(self) -> UiResponse:
        body = (
            "Telegram adapter is running.\n"
            "ops-core business functions are unavailable in this screen.\n"
            "No real business actions will be performed."
        )
        if self.reason:
            body += f"\n\nReason: {self.reason}"
        return UiResponse(
            title="Mock Home",
            body=body,
            banner=self.settings.mock_banner if self.settings.backend_show_mock_banner else None,
            source="mock",
            degraded=bool(self.reason),
            buttons=_default_buttons(),
        )

    def _status(self) -> UiResponse:
        return UiResponse(
            title="Adapter Status",
            body=(
                "adapter service status: ok\n"
                f"backend mode: {self.settings.backend_mode}\n"
                f"ops-core base URL: {self.settings.ops_core_base_url}\n"
                f"last ops-core call succeeded: {self.last_success}\n"
                f"last error: {self.last_error or 'none'}\n"
                f"current time: {datetime.now(timezone.utc).isoformat()}"
            ),
            banner=self.settings.mock_banner if self.settings.backend_show_mock_banner else None,
            source="mock",
            degraded=bool(self.reason),
            buttons=_default_buttons(),
        )

    def _mock_screen(self, action: str) -> UiResponse:
        title = action.replace("mock:", "Mock ").replace("_", " ").title()
        return UiResponse(
            title=title,
            body="Demo-only screen. No real business operation was performed.",
            banner=self.settings.mock_banner if self.settings.backend_show_mock_banner else None,
            source="mock",
            degraded=True,
            buttons=_default_buttons(),
        )

    def _business_unavailable(self, action: str, payload: dict[str, Any]) -> UiResponse:
        request = payload.get("text") or payload.get("request") or action
        return UiResponse(
            title="ops-core unavailable",
            body=(
                "Business functions are offline because ops-core is unavailable.\n"
                f"Requested action: {action}\n"
                f"Request: {request}\n"
                "No successful business action was created or executed."
            ),
            banner=self.settings.mock_banner if self.settings.backend_show_mock_banner else None,
            source="mock",
            success=False,
            degraded=True,
            buttons=[
                UiButton("Retry ops-core", "mock:retry_backend"),
                UiButton("Adapter Status", "system:adapter_status"),
                UiButton("Mock Home", "mock:home"),
            ],
        )


def _default_buttons() -> list[UiButton]:
    return [
        UiButton("Retry ops-core", "mock:retry_backend"),
        UiButton("Mock demo", "mock:demo"),
        UiButton("Adapter status", "system:adapter_status"),
        UiButton("Adapter logs", "mock:logs"),
        UiButton("Mock projects", "mock:projects"),
        UiButton("Mock reminders", "mock:reminders"),
        UiButton("Mock notifications", "mock:notifications"),
        UiButton("Mock settings", "mock:settings"),
    ]

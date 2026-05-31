from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class BackendUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class UiButton:
    text: str
    action: str


@dataclass(frozen=True)
class UiResponse:
    title: str
    body: str
    buttons: list[UiButton] = field(default_factory=list)
    banner: str | None = None
    source: str = "ops"
    success: bool = False
    degraded: bool = False


@dataclass(frozen=True)
class BackendHealth:
    status: str
    mode: str
    ops_core_base_url: str
    last_success: bool
    last_error: str | None = None


class BackendClient(Protocol):
    async def handle(self, action: str, payload: dict[str, Any]) -> UiResponse:
        ...

    async def health(self) -> BackendHealth:
        ...

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ProjectsResponse(BaseModel):
    ok: bool
    projects: list[str]


class CommandResponse(BaseModel):
    ok: bool
    project: str | None = None
    action: str | None = None
    message: str | None = None
    data: dict[str, Any] | None = None
    error: str | None = None


class NotificationPullResponse(BaseModel):
    ok: bool
    project: str | None = None
    action: str | None = None
    pushed_count: int | None = None
    message: str | None = None
    data: dict[str, Any] | None = None
    error: str | None = None

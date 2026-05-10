from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Header, HTTPException, status

from config import Settings, get_settings
from core.project_registry import ProjectRegistry


@dataclass(frozen=True)
class RequestContext:
    channel: str
    user_id: int


class AuthService:
    ACTIONS = {"projects", "status", "logs", "pull_notifications"}

    def __init__(self, settings: Settings, registry: ProjectRegistry):
        self.settings = settings
        self.registry = registry

    def authorize(
        self,
        *,
        authorization: str | None,
        channel: str | None,
        user_id: str | None,
        action: str,
        project: str | None = None,
    ) -> RequestContext:
        self._validate_token(authorization)
        if action not in self.ACTIONS:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "action_not_allowed")
        parsed_user_id = self._parse_user_id(user_id)
        if not self.settings.allowed_user_ids:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "user_not_allowed")
        if parsed_user_id not in self.settings.allowed_user_ids:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "user_not_allowed")
        if project is not None:
            self._validate_project_policy(project, parsed_user_id, action)
        return RequestContext(channel=channel or "unknown", user_id=parsed_user_id)

    def _validate_token(self, authorization: str | None) -> None:
        prefix = "Bearer "
        if not authorization or not authorization.startswith(prefix):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing_bearer_token")
        token = authorization[len(prefix) :].strip()
        if token != self.settings.ops_api_token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_api_token")

    def _parse_user_id(self, value: str | None) -> int:
        try:
            return int(value or "")
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_user_id") from exc

    def _validate_project_policy(self, project: str, user_id: int, action: str) -> None:
        project_config = self.registry.get_project(project)
        if project_config is None:
            return
        allowed_actions = project_config.get("allowed_actions")
        if isinstance(allowed_actions, list) and action not in set(map(str, allowed_actions)):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "action_not_allowed")
        allowed_users = _int_set(project_config.get("allowed_user_ids"))
        if allowed_users and user_id not in allowed_users:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "project_not_allowed")


def _int_set(value: Any) -> set[int]:
    if value is None:
        return set()
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, list):
        items = value
    else:
        return set()
    result: set[int] = set()
    for item in items:
        try:
            result.add(int(str(item).strip()))
        except ValueError:
            continue
    return result


def get_auth_context(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_channel: str | None = Header(default=None, alias="X-Channel"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> tuple[AuthService, str | None, str | None, str | None]:
    settings = get_settings()
    registry = ProjectRegistry(settings.projects_config_path)
    return AuthService(settings, registry), authorization, x_channel, x_user_id

from __future__ import annotations

from fastapi import APIRouter, Depends, Header

from api.schemas import NotificationPullResponse
from core.auth_service import get_auth_context
from core.factory import build_services


router = APIRouter(prefix="/api/projects")


@router.post("/{project}/pull-notifications", response_model=NotificationPullResponse)
def pull_notifications(
    project: str,
    x_chat_id: str | None = Header(default=None, alias="X-Chat-Id"),
    auth=Depends(get_auth_context),
) -> dict:
    auth_service, authorization, channel, user_id = auth
    context = auth_service.authorize(
        authorization=authorization,
        channel=channel,
        user_id=user_id,
        action="pull_notifications",
        project=project,
    )
    _, commands, audit = build_services(auth_service.settings)
    result = commands.pull_notifications(project, _parse_chat_id(x_chat_id))
    audit.write(
        context=context,
        action="pull_notifications",
        project=project,
        result=result,
    )
    return {key: value for key, value in result.items() if not key.startswith("_")}


def _parse_chat_id(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None

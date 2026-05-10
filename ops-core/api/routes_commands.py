from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.schemas import CommandResponse
from core.auth_service import get_auth_context
from core.factory import build_services


router = APIRouter(prefix="/api/projects")


@router.get("/{project}/status", response_model=CommandResponse)
def project_status(project: str, auth=Depends(get_auth_context)) -> dict:
    auth_service, authorization, channel, user_id = auth
    context = auth_service.authorize(
        authorization=authorization,
        channel=channel,
        user_id=user_id,
        action="status",
        project=project,
    )
    _, commands, audit = build_services(auth_service.settings)
    result = commands.status(project)
    audit.write(context=context, action="status", project=project, result=result)
    return _public(result)


@router.get("/{project}/logs", response_model=CommandResponse)
def project_logs(
    project: str,
    lines: int | None = Query(default=None, ge=1, le=300),
    auth=Depends(get_auth_context),
) -> dict:
    auth_service, authorization, channel, user_id = auth
    context = auth_service.authorize(
        authorization=authorization,
        channel=channel,
        user_id=user_id,
        action="logs",
        project=project,
    )
    _, commands, audit = build_services(auth_service.settings)
    result = commands.logs(project, lines)
    audit.write(context=context, action="logs", project=project, result=result)
    return _public(result)


def _public(result: dict) -> dict:
    return {key: value for key, value in result.items() if not key.startswith("_")}

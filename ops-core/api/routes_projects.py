from __future__ import annotations

from fastapi import APIRouter, Depends

from core.auth_service import get_auth_context
from core.factory import build_services
from api.schemas import ProjectsResponse


router = APIRouter(prefix="/api")


@router.get("/projects", response_model=ProjectsResponse)
def list_projects(auth=Depends(get_auth_context)) -> dict:
    auth_service, authorization, channel, user_id = auth
    context = auth_service.authorize(
        authorization=authorization,
        channel=channel,
        user_id=user_id,
        action="projects",
    )
    registry, _, audit = build_services(auth_service.settings)
    result = {"ok": True, "projects": registry.list_projects()}
    audit.write(context=context, action="projects", project=None, result=result)
    return result

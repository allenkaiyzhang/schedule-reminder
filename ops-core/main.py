from __future__ import annotations

import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.routes_commands import router as commands_router
from api.routes_notifications import router as notifications_router
from api.routes_projects import router as projects_router
from config import get_settings


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)

app = FastAPI(title="ops-core", version="0.1.0")
app.include_router(projects_router)
app.include_router(commands_router)
app.include_router(notifications_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "project": request.path_params.get("project"),
            "action": _action_from_path(request.url.path),
            "error": str(exc.detail),
            "message": str(exc.detail),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "ok": False,
            "project": request.path_params.get("project"),
            "action": _action_from_path(request.url.path),
            "error": "validation_error",
            "message": "请求参数无效",
        },
    )


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


def _action_from_path(path: str) -> str | None:
    if path.endswith("/status"):
        return "status"
    if path.endswith("/logs"):
        return "logs"
    if path.endswith("/pull-notifications"):
        return "pull_notifications"
    if path.endswith("/projects"):
        return "projects"
    return None


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.ops_api_host,
        port=settings.ops_api_port,
        reload=False,
    )

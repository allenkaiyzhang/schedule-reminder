from __future__ import annotations

from adapters.audit_log_adapter import AuditLogAdapter
from core.auth_service import RequestContext


class AuditService:
    def __init__(self, adapter: AuditLogAdapter):
        self.adapter = adapter

    def write(
        self,
        *,
        context: RequestContext,
        action: str,
        project: str | None,
        result: dict,
    ) -> None:
        self.adapter.write(
            channel=context.channel,
            user_id=context.user_id,
            action=action,
            project=project,
            success=bool(result.get("ok")),
            duration_ms=int(result.get("_duration_ms") or 0),
            message=str(result.get("message") or result.get("error") or ""),
        )

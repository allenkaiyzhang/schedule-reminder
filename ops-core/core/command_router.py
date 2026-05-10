from __future__ import annotations

from core.logs_service import LogsService
from core.notification_service import NotificationService
from core.status_service import StatusService


class CommandRouter:
    def __init__(
        self,
        *,
        status_service: StatusService,
        logs_service: LogsService,
        notification_service: NotificationService,
    ):
        self.status_service = status_service
        self.logs_service = logs_service
        self.notification_service = notification_service

    def status(self, project: str) -> dict:
        return self.status_service.get_status(project)

    def logs(self, project: str, lines: int | None) -> dict:
        return self.logs_service.get_logs(project, lines)

    def pull_notifications(self, project: str, chat_id: int | None) -> dict:
        return self.notification_service.pull_notifications(project, chat_id=chat_id)

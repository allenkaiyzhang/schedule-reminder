from __future__ import annotations

from adapters.audit_log_adapter import AuditLogAdapter
from adapters.notification_archive_adapter import TelegramNotificationAdapter
from adapters.sqlite_adapter import SQLiteAdapter
from adapters.ssh_adapter import SSHAdapter
from config import Settings, get_settings
from core.audit_service import AuditService
from core.command_router import CommandRouter
from core.logs_service import LogsService
from core.notification_service import NotificationService
from core.project_registry import ProjectRegistry
from core.status_service import StatusService


def build_services(settings: Settings | None = None) -> tuple[ProjectRegistry, CommandRouter, AuditService]:
    settings = settings or get_settings()
    registry = ProjectRegistry(settings.projects_config_path)
    ssh = SSHAdapter(
        key_path=str(settings.ssh_key_path),
        timeout_seconds=settings.ssh_timeout_seconds,
    )
    sqlite = SQLiteAdapter(settings.database_path)
    router = CommandRouter(
        status_service=StatusService(registry, ssh),
        logs_service=LogsService(registry, ssh, settings.default_log_lines),
        notification_service=NotificationService(
            registry=registry,
            ssh=ssh,
            sqlite=sqlite,
            notifier=TelegramNotificationAdapter(settings.telegram_bot_token),
            default_lines=settings.notification_pull_lines,
            default_chat_id=settings.telegram_notify_chat_id,
        ),
    )
    audit = AuditService(AuditLogAdapter(settings.log_dir))
    return registry, router, audit

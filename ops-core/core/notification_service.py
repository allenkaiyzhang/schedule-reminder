from __future__ import annotations

import json
from typing import Any

from adapters.notification_archive_adapter import TelegramNotificationAdapter
from adapters.sqlite_adapter import SQLiteAdapter
from adapters.ssh_adapter import SSHAdapter
from core.project_registry import ProjectRegistry


class NotificationService:
    def __init__(
        self,
        *,
        registry: ProjectRegistry,
        ssh: SSHAdapter,
        sqlite: SQLiteAdapter,
        notifier: TelegramNotificationAdapter,
        default_lines: int,
        default_chat_id: int | None,
    ):
        self.registry = registry
        self.ssh = ssh
        self.sqlite = sqlite
        self.notifier = notifier
        self.default_lines = default_lines
        self.default_chat_id = default_chat_id

    def pull_notifications(self, project: str, *, chat_id: int | None = None) -> dict:
        target_chat_id = chat_id or self.default_chat_id
        if target_chat_id is None:
            return _error(project, "pull_notifications", "missing_chat_id", "未配置通知 chat_id", 0)

        config = self.registry.get_project(project)
        if config is None:
            return _error(project, "pull_notifications", "unknown_project", f"未知项目：{project}", 0)
        if "notifications" not in (config.get("scripts") or {}):
            return _error(project, "pull_notifications", "script_not_configured", f"项目 {project} 未配置 notifications 脚本", 0)

        lines = min(max(1, self.default_lines), 300)
        result = self.ssh.run_script(config, "notifications", [str(lines)])
        if result.timed_out:
            return _error(project, "pull_notifications", "ssh_timeout", "远程执行超时", result.duration_ms)
        if not result.success:
            return _error(
                project,
                "pull_notifications",
                "ssh_failed",
                "远程脚本执行失败\n" + ((result.stderr or "")[-1000:] or "无 stderr 输出"),
                result.duration_ms,
            )

        fetched = invalid = skipped = pushed = failed = 0
        for raw in result.stdout.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            fetched += 1
            notification = _parse_notification(raw)
            if notification is None:
                invalid += 1
                continue
            notification_id = str(notification["id"])
            if self.sqlite.is_notification_pushed(notification_id):
                skipped += 1
                continue
            try:
                self.notifier.send_message(
                    chat_id=target_chat_id,
                    text=format_notification_message(project, notification),
                )
            except Exception:
                failed += 1
                continue
            self.sqlite.mark_notification_pushed(
                notification_id=notification_id,
                project=project,
                level=_optional_text(notification.get("level")),
                title=_optional_text(notification.get("title")),
                time_value=_optional_text(notification.get("time")),
            )
            pushed += 1

        return {
            "ok": True,
            "project": project,
            "action": "pull_notifications",
            "pushed_count": pushed,
            "message": (
                f"通知拉取完成 fetched={fetched} pushed={pushed} "
                f"skipped={skipped} invalid={invalid} failed={failed}"
            ),
            "data": {
                "fetched": fetched,
                "pushed": pushed,
                "skipped": skipped,
                "invalid": invalid,
                "failed": failed,
            },
            "_duration_ms": result.duration_ms,
        }


def _parse_notification(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    notification_id = data.get("id")
    if notification_id is None or str(notification_id).strip() == "":
        return None
    return data


def format_notification_message(project: str, notification: dict[str, Any]) -> str:
    level = _optional_text(notification.get("level")) or "INFO"
    title = _optional_text(notification.get("title")) or "无标题通知"
    time_value = _optional_text(notification.get("time")) or "未知"
    body = _optional_text(
        notification.get("body")
        or notification.get("content")
        or notification.get("message")
        or ""
    )
    lines = [f"[{project}] {level.upper()}", f"标题：{title}", f"时间：{time_value}"]
    if body:
        lines.extend(["", "正文：", body])
    return _tail("\n".join(lines), 3500)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _error(project: str, action: str, error: str, message: str, duration_ms: int) -> dict:
    return {
        "ok": False,
        "project": project,
        "action": action,
        "error": error,
        "message": message,
        "_duration_ms": duration_ms,
    }


def _tail(text: str, length: int) -> str:
    return text[-length:] if len(text) > length else text

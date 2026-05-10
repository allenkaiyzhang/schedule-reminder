from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from telegram import Bot
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from adapters.ssh_adapter import run_remote_script
from audit import write_audit
from config import Settings
from db import Database


logger = logging.getLogger(__name__)
MAX_TELEGRAM_TEXT = 3500
PROJECT_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class NotificationPullResult:
    project: str
    fetched: int = 0
    invalid: int = 0
    skipped: int = 0
    pushed: int = 0
    failed: int = 0
    error: str | None = None


async def pull_notifications_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    if not settings.notification_pull_enabled:
        return
    if settings.telegram_notify_chat_id is None:
        logger.warning("通知拉取已启用，但 TELEGRAM_NOTIFY_CHAT_ID 未配置")
        return

    projects = settings.notification_pull_projects or []
    for project in projects:
        try:
            result = await pull_project_notifications(
                db=context.application.bot_data["db"],
                bot=context.application.bot,
                settings=settings,
                project_name=project,
                chat_id=settings.telegram_notify_chat_id,
            )
            _audit(settings, None, result)
        except Exception:
            logger.exception("定时拉取通知失败 project=%s", project)


async def pull_project_notifications(
    *,
    db: Database,
    bot: Bot,
    settings: Settings,
    project_name: str,
    chat_id: int,
) -> NotificationPullResult:
    if not PROJECT_NAME_RE.fullmatch(project_name):
        return NotificationPullResult(project=project_name, error="项目名称格式无效")

    projects = load_projects(settings)
    project_config = projects.get(project_name)
    if project_config is None:
        return NotificationPullResult(project=project_name, error="未知项目")

    scripts = project_config.get("scripts") or {}
    if "notifications" not in scripts:
        return NotificationPullResult(
            project=project_name,
            error="projects.yaml 未配置 scripts.notifications",
        )

    runnable_config = dict(project_config)
    runnable_config["_ssh"] = {
        "key_path": settings.ssh_key_path,
        "timeout_seconds": settings.ssh_timeout_seconds,
    }

    lines = max(1, min(settings.notification_pull_lines, 300))
    result = await asyncio.to_thread(
        run_remote_script,
        runnable_config,
        "notifications",
        [str(lines)],
    )
    if result.timed_out:
        return NotificationPullResult(project=project_name, error="远程执行超时")
    if not result.success:
        message = result.stderr.strip() or f"远程脚本退出码：{result.returncode}"
        return NotificationPullResult(project=project_name, error=message[:1000])

    fetched = invalid = skipped = pushed = failed = 0
    for raw_line in result.stdout.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        fetched += 1
        notification = _parse_notification(raw_line)
        if notification is None:
            invalid += 1
            logger.warning("跳过无效通知 JSON project=%s line=%s", project_name, raw_line[:500])
            continue

        notification_id = str(notification["id"])
        if db.is_notification_pushed(notification_id):
            skipped += 1
            continue

        text = format_notification_message(project_name, notification)
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except TelegramError:
            failed += 1
            logger.exception(
                "Telegram 通知发送失败 project=%s notification_id=%s",
                project_name,
                notification_id,
            )
            continue

        db.mark_notification_pushed(
            notification_id=notification_id,
            project=project_name,
            level=_optional_text(notification.get("level")),
            title=_optional_text(notification.get("title")),
            time_value=_optional_text(notification.get("time")),
        )
        pushed += 1

    return NotificationPullResult(
        project=project_name,
        fetched=fetched,
        invalid=invalid,
        skipped=skipped,
        pushed=pushed,
        failed=failed,
    )


def _parse_notification(raw_line: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    notification_id = data.get("id")
    if notification_id is None or str(notification_id).strip() == "":
        return None
    return data


def load_projects(settings: Settings) -> dict[str, dict[str, Any]]:
    path = Path(settings.projects_config_path)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    projects = data.get("projects") or {}
    if not isinstance(projects, dict):
        return {}
    return {
        str(name): config
        for name, config in projects.items()
        if isinstance(config, dict)
    }


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
    attachments = notification.get("attachments") or notification.get("files") or []
    if isinstance(attachments, str):
        attachments = [attachments]
    if not isinstance(attachments, list):
        attachments = []

    lines = [
        f"[{project}] {level.upper()}",
        f"标题：{title}",
        f"时间：{time_value}",
    ]
    if body:
        lines.extend(["", "正文：", body])
    if attachments:
        lines.extend(["", "附件："])
        lines.extend(f"- {item}" for item in attachments if str(item).strip())
    return _truncate("\n".join(lines), MAX_TELEGRAM_TEXT)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    suffix = "\n\n……内容过长，已截断"
    return text[: max_length - len(suffix)] + suffix


def _audit(
    settings: Settings,
    user_id: int | None,
    result: NotificationPullResult,
) -> None:
    success = result.error is None and result.failed == 0
    message = (
        result.error
        or f"fetched={result.fetched} invalid={result.invalid} "
        f"skipped={result.skipped} pushed={result.pushed} failed={result.failed}"
    )
    write_audit(
        user_id,
        "pull_notifications",
        result.project,
        success,
        0,
        message,
        log_path=settings.log_dir / "audit.log",
    )

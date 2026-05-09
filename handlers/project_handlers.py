from __future__ import annotations

import re
import asyncio
from pathlib import Path
from typing import Any

import yaml
from telegram import Update
from telegram.ext import ContextTypes

from adapters.ssh_adapter import run_remote_script
from audit import write_audit
from auth import is_allowed_user
from config import Settings


MAX_LOG_LINES = 300
MAX_TELEGRAM_TEXT = 3500
PROJECT_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


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


async def projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _settings(context)
    if not await _guard(update, settings):
        return

    items = load_projects(settings)
    if not items:
        await update.effective_message.reply_text("暂无可用项目。")
        _audit(settings, update.effective_user.id if update.effective_user else None, "projects", "", True, 0, "empty")
        return

    lines = ["可用项目："]
    lines.extend(f"- {name}" for name in sorted(items))
    await update.effective_message.reply_text("\n".join(lines))
    _audit(settings, update.effective_user.id if update.effective_user else None, "projects", "", True, 0, "ok")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_project_script(update, context, command="status", script_name="status")


async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _run_project_script(update, context, command="logs", script_name="logs")


async def _run_project_script(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    command: str,
    script_name: str,
) -> None:
    settings = _settings(context)
    user_id = update.effective_user.id if update.effective_user else None
    if not await _guard(update, settings):
        return

    message = update.effective_message
    if command == "status" and len(context.args) != 1:
        await message.reply_text(f"用法：/{command} <project>")
        return
    if command == "logs" and len(context.args) not in {1, 2}:
        await message.reply_text(f"用法：/{command} <project> [lines]")
        return

    project_name = context.args[0] if context.args else ""
    if not project_name:
        await message.reply_text(f"用法：/{command} <project>" + (" [lines]" if command == "logs" else ""))
        return
    if not PROJECT_NAME_RE.fullmatch(project_name):
        await message.reply_text("项目名称格式无效，请使用 /projects 查看可用项目")
        return

    projects_config = load_projects(settings)
    project_config = projects_config.get(project_name)
    if project_config is None:
        await message.reply_text(f"未知项目：{project_name}\n请使用 /projects 查看可用项目")
        return

    scripts = project_config.get("scripts") or {}
    if script_name not in scripts:
        await message.reply_text(f"项目 {project_name} 未配置 {script_name} 脚本")
        _audit(settings, user_id, command, project_name, False, 0, "script not configured")
        return

    args: list[str] = []
    if command == "logs":
        lines = _parse_log_lines(context.args[1:] if len(context.args) > 1 else [], settings)
        if lines is None:
            await message.reply_text("lines 必须是 1 到 300 之间的整数")
            return
        args.append(str(lines))

    runnable_config = dict(project_config)
    runnable_config["_ssh"] = {
        "key_path": settings.ssh_key_path,
        "timeout_seconds": settings.ssh_timeout_seconds,
    }

    result = await asyncio.to_thread(run_remote_script, runnable_config, script_name, args)
    if result.timed_out:
        await message.reply_text("远程执行超时")
        _audit(settings, user_id, command, project_name, False, result.duration_ms, "timeout")
        return

    if not result.success:
        stderr = _tail(result.stderr, 1000) or "无 stderr 输出"
        await message.reply_text(f"远程脚本执行失败\n{stderr}")
        _audit(settings, user_id, command, project_name, False, result.duration_ms, stderr)
        return

    output = _tail(result.stdout.strip(), MAX_TELEGRAM_TEXT)
    if not output:
        output = "命令执行完成，但没有输出"
    await message.reply_text(output)
    _audit(settings, user_id, command, project_name, True, result.duration_ms, "ok")


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


async def _guard(update: Update, settings: Settings) -> bool:
    user = update.effective_user
    if user is not None and is_allowed_user(user.id, settings):
        return True
    if update.effective_message is not None:
        await update.effective_message.reply_text("你没有权限使用项目控制台。")
    return False


def _parse_log_lines(args: list[str], settings: Settings) -> int | None:
    if not args:
        return min(max(1, settings.default_log_lines), MAX_LOG_LINES)
    if len(args) != 1:
        return None
    try:
        lines = int(args[0])
    except ValueError:
        return None
    if lines < 1:
        return None
    return min(lines, MAX_LOG_LINES)


def _tail(text: str, length: int) -> str:
    return text[-length:] if len(text) > length else text


def _audit(
    settings: Settings,
    user_id: int | None,
    command: str,
    project: str,
    success: bool,
    duration_ms: int,
    message: str,
) -> None:
    write_audit(
        user_id,
        command,
        project,
        success,
        duration_ms,
        message,
        log_path=settings.log_dir / "audit.log",
    )

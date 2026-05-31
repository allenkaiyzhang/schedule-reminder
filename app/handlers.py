from __future__ import annotations

from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from app.config import Settings
from app.reminder_service import USAGE, format_reminder_time, parse_reminder
from app.reminder_store import ReminderStore


MAX_LOG_LINES = 200


def _is_allowed(update: Update, settings: Settings) -> bool:
    user = update.effective_user
    return bool(user and str(user.id) in settings.allowed_user_ids)


async def _reject(update: Update, settings: Settings) -> bool:
    if _is_allowed(update, settings):
        return False
    if update.message:
        await update.message.reply_text("This bot is private. Your Telegram user is not allowed.")
    return True


def _deps(context: ContextTypes.DEFAULT_TYPE) -> tuple[Settings, ReminderStore]:
    return context.application.bot_data["settings"], context.application.bot_data["store"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, _ = _deps(context)
    if await _reject(update, settings):
        return
    await update.message.reply_text(_help_text())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, _ = _deps(context)
    if await _reject(update, settings):
        return
    await update.message.reply_text(_help_text())


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, store = _deps(context)
    if await _reject(update, settings):
        return
    if update.effective_user is None or update.effective_chat is None or update.message is None:
        return
    raw = " ".join(context.args)
    try:
        parsed = parse_reminder(raw, settings.timezone)
    except ValueError:
        await update.message.reply_text(USAGE)
        return
    reminder = store.create(
        user_id=str(update.effective_user.id),
        chat_id=str(update.effective_chat.id),
        text=parsed.text,
        remind_at=parsed.remind_at.isoformat(),
        timezone_name=parsed.timezone_name,
    )
    await update.message.reply_text(
        f"Created reminder #{reminder.id}: "
        f"{format_reminder_time(reminder.remind_at, reminder.timezone)}"
    )


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, store = _deps(context)
    if await _reject(update, settings):
        return
    if update.effective_user is None or update.message is None:
        return
    reminders = store.list_for_user(str(update.effective_user.id))
    if not reminders:
        await update.message.reply_text("No active or paused reminders.")
        return
    lines = [
        f"#{item.id} [{item.status}] {format_reminder_time(item.remind_at, item.timezone)} - {item.text}"
        for item in reminders
    ]
    await update.message.reply_text("\n".join(lines))


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_status(update, context, "deleted", "Deleted")


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_status(update, context, "paused", "Paused")


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _set_status(update, context, "active", "Resumed")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, store = _deps(context)
    if await _reject(update, settings):
        return
    counts = store.counts()
    await update.message.reply_text(
        "schedule-reminder status\n"
        f"service={settings.service_name}\n"
        f"bot_enabled={settings.enable_bot}\n"
        f"telegram_send_disabled={settings.disable_telegram_send}\n"
        f"counts={counts}"
    )


async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings, _ = _deps(context)
    if await _reject(update, settings):
        return
    lines = _parse_lines(context.args)
    text = _tail_file(settings.log_file, lines)
    await update.message.reply_text(text or "No local log output yet.")


async def _set_status(
    update: Update, context: ContextTypes.DEFAULT_TYPE, new_status: str, label: str
) -> None:
    settings, store = _deps(context)
    if await _reject(update, settings):
        return
    if update.effective_user is None or update.message is None:
        return
    reminder_id = _first_int(context.args)
    if reminder_id is None:
        await update.message.reply_text("Usage: /delete <id> or /pause <id> or /resume <id>")
        return
    ok = store.set_status_for_user(reminder_id, str(update.effective_user.id), new_status)
    await update.message.reply_text(f"{label} reminder #{reminder_id}." if ok else "Reminder not found.")


def _first_int(args: list[str]) -> int | None:
    if not args:
        return None
    try:
        return int(args[0])
    except ValueError:
        return None


def _parse_lines(args: list[str]) -> int:
    if not args:
        return 80
    try:
        return max(1, min(MAX_LOG_LINES, int(args[0])))
    except ValueError:
        return 80


def _tail_file(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as file:
        content = file.readlines()[-lines:]
    return "".join(content)[-3500:]


def _help_text() -> str:
    return (
        "schedule-reminder commands:\n"
        "/remind 2026-06-01 09:30 Take medicine\n"
        "/remind 2026-06-01 09:30 Asia/Shanghai Take medicine\n"
        "/remind in 10m Take a break\n"
        "/remind in 2h Check report\n"
        "/list\n"
        "/pause <id>\n"
        "/resume <id>\n"
        "/delete <id>\n"
        "/status\n"
        "/logs [lines]"
    )

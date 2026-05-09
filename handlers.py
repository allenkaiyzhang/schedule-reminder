from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from config import Settings
from db import Database
from parser import ParseError, parse_add_command, reminder_times
from reminder import format_schedule_time


logger = logging.getLogger(__name__)

HELP_TEXT = """Commands:
/start - Start the bot
/help - Show help
/add YYYY-MM-DD HH:MM title - Add a schedule
/list - List pending schedules
/today - List today's schedules
/tomorrow - List tomorrow's schedules
/done ID - Mark a schedule done
/delete ID - Delete a schedule
"""


def _is_allowed(settings: Settings, update: Update) -> bool:
    user = update.effective_user
    if not settings.allowed_user_ids:
        return True
    return user is not None and user.id in settings.allowed_user_ids


async def _guard(update: Update, settings: Settings) -> bool:
    if _is_allowed(settings, update):
        return True
    if update.effective_message is not None:
        await update.effective_message.reply_text("You are not allowed to use this bot.")
    return False


def _deps(context: ContextTypes.DEFAULT_TYPE) -> tuple[Database, Settings]:
    return context.application.bot_data["db"], context.application.bot_data["settings"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, settings = _deps(context)
    if not await _guard(update, settings):
        return
    await update.effective_message.reply_text(
        "Hi. I can help manage schedules and reminders.\n\n" + HELP_TEXT
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, settings = _deps(context)
    if not await _guard(update, settings):
        return
    await update.effective_message.reply_text(HELP_TEXT)


async def add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings = _deps(context)
    if not await _guard(update, settings):
        return

    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if message is None or user is None or chat is None:
        return

    try:
        parsed = parse_add_command(message.text or "", settings.default_timezone)
        remind_at_values = [
            dt.astimezone(timezone.utc).isoformat(timespec="seconds")
            for dt in reminder_times(
                parsed.utc_start_at,
                settings.default_remind_before_minutes,
            )
        ]
        schedule_id = db.create_schedule(
            user_id=user.id,
            chat_id=chat.id,
            title=parsed.title,
            start_at=parsed.utc_start_at.isoformat(timespec="seconds"),
            timezone_name=parsed.timezone_name,
            remind_at_values=remind_at_values,
        )
    except ParseError as exc:
        await message.reply_text(str(exc))
        return
    except sqlite3.Error:
        await message.reply_text("Failed to save schedule. Please try again later.")
        return

    await message.reply_text(
        f"Added schedule #{schedule_id}\n"
        f"Time: {parsed.local_start_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"Title: {parsed.title}"
    )


async def list_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings = _deps(context)
    if not await _guard(update, settings):
        return
    await _send_schedule_list(update, db.list_schedules(user_id=update.effective_user.id))


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings = _deps(context)
    if not await _guard(update, settings):
        return
    start_utc, end_utc = _local_day_bounds(settings.default_timezone, days_offset=0)
    await _send_schedule_list(
        update,
        db.list_schedules(
            user_id=update.effective_user.id,
            start_from=start_utc,
            start_to=end_utc,
        ),
    )


async def tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings = _deps(context)
    if not await _guard(update, settings):
        return
    start_utc, end_utc = _local_day_bounds(settings.default_timezone, days_offset=1)
    await _send_schedule_list(
        update,
        db.list_schedules(
            user_id=update.effective_user.id,
            start_from=start_utc,
            start_to=end_utc,
        ),
    )


async def mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings = _deps(context)
    if not await _guard(update, settings):
        return
    schedule_id = _first_int_arg(context)
    if schedule_id is None:
        await update.effective_message.reply_text("Usage: /done ID")
        return
    try:
        ok = db.mark_done(schedule_id=schedule_id, user_id=update.effective_user.id)
    except sqlite3.Error:
        await update.effective_message.reply_text("Failed to update schedule.")
        return
    await update.effective_message.reply_text(
        f"Marked #{schedule_id} as done." if ok else "Schedule not found."
    )


async def delete_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings = _deps(context)
    if not await _guard(update, settings):
        return
    schedule_id = _first_int_arg(context)
    if schedule_id is None:
        await update.effective_message.reply_text("Usage: /delete ID")
        return
    try:
        ok = db.delete_schedule(schedule_id=schedule_id, user_id=update.effective_user.id)
    except sqlite3.Error:
        await update.effective_message.reply_text("Failed to delete schedule.")
        return
    await update.effective_message.reply_text(
        f"Deleted #{schedule_id}." if ok else "Schedule not found."
    )


def _first_int_arg(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    if not context.args:
        return None
    try:
        return int(context.args[0])
    except ValueError:
        return None


def _local_day_bounds(timezone_name: str, *, days_offset: int) -> tuple[str, str]:
    tz = ZoneInfo(timezone_name)
    local_today = datetime.now(tz).date()
    start = datetime.combine(
        local_today + timedelta(days=days_offset),
        datetime.min.time(),
        tzinfo=tz,
    )
    end = start + timedelta(days=1)
    return (
        start.astimezone(timezone.utc).isoformat(timespec="seconds"),
        end.astimezone(timezone.utc).isoformat(timespec="seconds"),
    )


async def _send_schedule_list(update: Update, rows) -> None:
    message = update.effective_message
    if not rows:
        await message.reply_text("No pending schedules.")
        return

    lines = ["Pending schedules:"]
    for row in rows:
        when = format_schedule_time(row["start_at"], row["timezone"])
        lines.append(f"#{row['id']} | {when} | {row['title']}")
    await message.reply_text("\n".join(lines))

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Bot


def parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def format_schedule_time(start_at: str, timezone_name: str) -> str:
    dt = parse_iso_datetime(start_at).astimezone(ZoneInfo(timezone_name))
    return dt.strftime("%Y-%m-%d %H:%M")


async def send_reminder(bot: Bot, reminder_row) -> None:
    when = format_schedule_time(reminder_row["start_at"], reminder_row["timezone"])
    text = (
        "Schedule reminder\n"
        f"ID: {reminder_row['schedule_id']}\n"
        f"Time: {when}\n"
        f"Title: {reminder_row['title']}"
    )
    await bot.send_message(chat_id=reminder_row["chat_id"], text=text)

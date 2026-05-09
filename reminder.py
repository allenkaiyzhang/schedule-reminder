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
    lines = [
        "日程提醒",
        f"编号：{reminder_row['schedule_id']}",
        f"时间：{when}",
        f"标题：{reminder_row['title']}",
    ]
    if reminder_row["description"]:
        lines.append(f"备注：{reminder_row['description']}")
    if reminder_row["category"]:
        lines.append(f"分类：{reminder_row['category']}")
    lines.append("")
    lines.append("可使用 /snooze 10m 延后最近提醒，或 /done 编号 完成任务。")
    await bot.send_message(chat_id=reminder_row["chat_id"], text="\n".join(lines))

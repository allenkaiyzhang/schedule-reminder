from __future__ import annotations

import calendar
import logging
from datetime import datetime, timedelta

from db import Database, parse_iso, text_to_minutes
from parser import reminder_times


logger = logging.getLogger("scheduler")


class RecurrenceWorker:
    def __init__(self, *, db: Database, default_remind_before_minutes: list[int]):
        self.db = db
        self.default_remind_before_minutes = default_remind_before_minutes

    async def run(self) -> None:
        for row in self.db.recurring_done_schedules():
            try:
                self._generate_next(row)
                self.db.mark_recurrence_generated(row["id"])
            except Exception:
                logger.exception("生成重复任务失败 schedule_id=%s", row["id"])

    def _generate_next(self, row) -> None:
        rule = row["repeat_rule"]
        start_at = parse_iso(row["start_at"])
        next_start = _next_start(start_at, rule)
        minutes = text_to_minutes(row["reminder_minutes"], self.default_remind_before_minutes)
        remind_values = [
            item.isoformat(timespec="seconds")
            for item in reminder_times(next_start, minutes)
        ]
        self.db.create_schedule(
            user_id=row["user_id"],
            chat_id=row["chat_id"],
            title=row["title"],
            description=row["description"],
            start_at=next_start.isoformat(timespec="seconds"),
            timezone_name=row["timezone"],
            repeat_rule=rule,
            remind_at_values=remind_values,
            reminder_minutes=minutes,
            category=row["category"],
            priority=row["priority"],
            ai_generated=bool(row["ai_generated"]),
            source_schedule_id=row["id"],
        )


def _next_start(start_at: datetime, rule: str) -> datetime:
    if rule == "daily":
        return start_at + timedelta(days=1)
    if rule == "weekly":
        return start_at + timedelta(weeks=1)
    if rule == "monthly":
        year = start_at.year + (1 if start_at.month == 12 else 0)
        month = 1 if start_at.month == 12 else start_at.month + 1
        max_day = calendar.monthrange(year, month)[1]
        return start_at.replace(year=year, month=month, day=min(start_at.day, max_day))
    raise ValueError(f"不支持的重复规则：{rule}")

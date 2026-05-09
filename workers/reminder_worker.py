from __future__ import annotations

import logging
from datetime import datetime, timezone

from telegram import Bot

from db import Database
from reminder import send_reminder


logger = logging.getLogger("scheduler")


class ReminderWorker:
    def __init__(self, *, db: Database, bot: Bot):
        self.db = db
        self.bot = bot

    async def run(self) -> None:
        self.db.cancel_orphan_pending_reminders()
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for reminder_row in self.db.due_reminders(now_iso=now_iso):
            try:
                await send_reminder(self.bot, reminder_row)
                self.db.mark_reminder_sent(reminder_row["reminder_id"])
            except Exception:
                logger.exception("发送提醒失败 reminder_id=%s", reminder_row["reminder_id"])

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram import Bot

from db import Database
from reminder import send_reminder


logger = logging.getLogger(__name__)


class ReminderScheduler:
    def __init__(self, *, db: Database, bot: Bot, interval_seconds: int):
        self.db = db
        self.bot = bot
        self.interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        logger.info("Reminder scheduler started")
        while not self._stop_event.is_set():
            try:
                await self.scan_once()
            except Exception:
                logger.exception("Reminder scan failed")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self.interval_seconds
                )
            except asyncio.TimeoutError:
                pass
        logger.info("Reminder scheduler stopped")

    def stop(self) -> None:
        self._stop_event.set()

    async def scan_once(self) -> None:
        self.db.cancel_orphan_pending_reminders()
        now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for reminder_row in self.db.due_reminders(now_iso=now_iso):
            try:
                await send_reminder(self.bot, reminder_row)
                self.db.mark_reminder_sent(reminder_row["reminder_id"])
            except Exception:
                logger.exception(
                    "Failed to send reminder id=%s",
                    reminder_row["reminder_id"],
                )

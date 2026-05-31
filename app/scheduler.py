from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot

from app.reminder_service import format_reminder_time
from app.reminder_store import ReminderStore


logger = logging.getLogger(__name__)


class ReminderScheduler:
    def __init__(
        self,
        *,
        store: ReminderStore,
        bot_token: str,
        timezone_name: str,
        disable_send: bool,
        max_instances: int,
        coalesce: bool,
    ):
        self.store = store
        self.bot = Bot(bot_token) if bot_token else None
        self.disable_send = disable_send
        self.scheduler = AsyncIOScheduler(timezone=timezone_name)
        self.max_instances = max_instances
        self.coalesce = coalesce

    def start(self) -> None:
        self.scheduler.add_job(
            self.process_due,
            IntervalTrigger(seconds=30),
            id="reminder_due_scan",
            replace_existing=True,
            max_instances=self.max_instances,
            coalesce=self.coalesce,
        )
        self.scheduler.start()
        logger.info("Reminder scheduler started")

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Reminder scheduler stopped")

    async def process_due(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for reminder in self.store.due_active(now):
            if self.disable_send:
                logger.info("Telegram send disabled; leaving reminder active id=%s", reminder.id)
                continue
            if self.bot is None:
                logger.error("Telegram bot token missing; cannot send reminder id=%s", reminder.id)
                self.store.mark_failed(reminder.id)
                continue
            try:
                when = format_reminder_time(reminder.remind_at, reminder.timezone)
                await self.bot.send_message(
                    chat_id=reminder.chat_id,
                    text=f"Reminder #{reminder.id}\n{when}\n{reminder.text}",
                )
                self.store.mark_sent(reminder.id)
                logger.info("Reminder sent id=%s chat_id=%s", reminder.id, reminder.chat_id)
            except Exception:
                logger.exception("Failed to send reminder id=%s", reminder.id)
                self.store.mark_failed(reminder.id)

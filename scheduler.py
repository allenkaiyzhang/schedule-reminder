from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot

from ai.client import AIProvider
from config import Settings
from db import Database
from workers.cleanup_worker import CleanupWorker
from workers.daily_summary_worker import DailySummaryWorker
from workers.recurrence_worker import RecurrenceWorker
from workers.reminder_worker import ReminderWorker


logger = logging.getLogger("scheduler")


class BotScheduler:
    def __init__(
        self,
        *,
        db: Database,
        bot: Bot,
        settings: Settings,
        ai_provider: AIProvider,
    ):
        self.db = db
        self.bot = bot
        self.settings = settings
        self.ai_provider = ai_provider
        self.timezone = ZoneInfo(settings.default_timezone)
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)

    def start(self) -> None:
        reminder_worker = ReminderWorker(db=self.db, bot=self.bot)
        recurrence_worker = RecurrenceWorker(
            db=self.db,
            default_remind_before_minutes=self.settings.default_remind_before_minutes,
        )
        cleanup_worker = CleanupWorker(db=self.db)
        summary_worker = DailySummaryWorker(
            db=self.db,
            bot=self.bot,
            ai_provider=self.ai_provider,
            timezone_name=self.settings.default_timezone,
        )

        self.scheduler.add_job(
            reminder_worker.run,
            IntervalTrigger(seconds=self.settings.check_interval_seconds),
            id="reminder_worker",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.add_job(
            recurrence_worker.run,
            IntervalTrigger(minutes=5),
            id="recurrence_worker",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.add_job(
            cleanup_worker.run,
            IntervalTrigger(minutes=10),
            id="cleanup_worker",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.add_job(
            summary_worker.send_morning_summary,
            CronTrigger(
                hour=self.settings.morning_summary_hour,
                minute=0,
                timezone=self.timezone,
            ),
            id="morning_summary_worker",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.add_job(
            summary_worker.send_evening_summary,
            CronTrigger(
                hour=self.settings.evening_summary_hour,
                minute=0,
                timezone=self.timezone,
            ),
            id="evening_summary_worker",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        self.scheduler.start()
        for job in self.scheduler.get_jobs():
            logger.info("任务已注册 id=%s next_run_time=%s", job.id, job.next_run_time)
        logger.info("APScheduler 已启动 timezone=%s", self.timezone)

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler 已停止")

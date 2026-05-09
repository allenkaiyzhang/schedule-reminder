from __future__ import annotations

import asyncio
import logging

from telegram.ext import Application, CommandHandler

from config import get_settings
from db import Database
from handlers import (
    add_schedule,
    delete_schedule,
    help_command,
    list_schedules,
    mark_done,
    start,
    today,
    tomorrow,
)
from scheduler import ReminderScheduler


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _post_init(application: Application) -> None:
    scheduler = ReminderScheduler(
        db=application.bot_data["db"],
        bot=application.bot,
        interval_seconds=application.bot_data["settings"].check_interval_seconds,
    )
    application.bot_data["reminder_scheduler"] = scheduler
    application.bot_data["reminder_task"] = asyncio.create_task(scheduler.start())


async def _post_shutdown(application: Application) -> None:
    scheduler: ReminderScheduler | None = application.bot_data.get("reminder_scheduler")
    task: asyncio.Task | None = application.bot_data.get("reminder_task")
    if scheduler is not None:
        scheduler.stop()
    if task is not None:
        await task


def build_application() -> Application:
    settings = get_settings()
    db = Database(settings.database_path)

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    application.bot_data["settings"] = settings
    application.bot_data["db"] = db

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_schedule))
    application.add_handler(CommandHandler("list", list_schedules))
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("tomorrow", tomorrow))
    application.add_handler(CommandHandler("done", mark_done))
    application.add_handler(CommandHandler("delete", delete_schedule))
    return application


def main() -> None:
    application = build_application()
    logger.info("Telegram schedule bot is starting")
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()

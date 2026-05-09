from __future__ import annotations

import importlib.util
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from ai import build_ai_provider
from config import Settings, get_settings
from db import Database
from handlers import (
    add_schedule,
    delete_schedule,
    edit_schedule,
    help_command,
    list_schedules,
    mark_done,
    natural_language_schedule,
    remind,
    repeat,
    snooze,
    start,
    today,
    tomorrow,
)
from scheduler import BotScheduler


logger = logging.getLogger(__name__)


def _load_project_handlers():
    path = Path(__file__).with_name("handlers") / "project_handlers.py"
    spec = importlib.util.spec_from_file_location("project_handlers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load project handlers")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def setup_logging(settings: Settings) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    files = {
        "": settings.log_dir / "bot.log",
        "scheduler": settings.log_dir / "scheduler.log",
        "ai": settings.log_dir / "ai.log",
    }
    for logger_name, path in files.items():
        handler = RotatingFileHandler(
            path,
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(formatter)
        target = logging.getLogger(logger_name)
        target.addHandler(handler)
        if logger_name:
            target.setLevel(logging.INFO)
            target.propagate = True


async def _post_init(application: Application) -> None:
    bot_scheduler = BotScheduler(
        db=application.bot_data["db"],
        bot=application.bot,
        settings=application.bot_data["settings"],
        ai_provider=application.bot_data["ai_provider"],
    )
    application.bot_data["bot_scheduler"] = bot_scheduler
    bot_scheduler.start()


async def _post_shutdown(application: Application) -> None:
    bot_scheduler: BotScheduler | None = application.bot_data.get("bot_scheduler")
    if bot_scheduler is not None:
        await bot_scheduler.shutdown()


def build_application() -> Application:
    settings = get_settings()
    setup_logging(settings)
    db = Database(
        settings.database_path,
        busy_timeout_ms=settings.sqlite_busy_timeout_ms,
    )
    ai_provider = build_ai_provider(settings)

    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )
    application.bot_data["settings"] = settings
    application.bot_data["db"] = db
    application.bot_data["ai_provider"] = ai_provider

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add", add_schedule))
    application.add_handler(CommandHandler("list", list_schedules))
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("tomorrow", tomorrow))
    application.add_handler(CommandHandler("edit", edit_schedule))
    application.add_handler(CommandHandler("snooze", snooze))
    application.add_handler(CommandHandler("repeat", repeat))
    application.add_handler(CommandHandler("remind", remind))
    application.add_handler(CommandHandler("done", mark_done))
    application.add_handler(CommandHandler("delete", delete_schedule))

    project_handlers = _load_project_handlers()
    application.add_handler(CommandHandler("projects", project_handlers.projects))
    application.add_handler(CommandHandler("status", project_handlers.status))
    application.add_handler(CommandHandler("logs", project_handlers.logs))

    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, natural_language_schedule)
    )
    return application


def main() -> None:
    application = build_application()
    logger.info("Telegram AI 日程助手启动中")
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()

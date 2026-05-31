from __future__ import annotations

from telegram.ext import Application, CommandHandler

from app import handlers
from app.config import Settings
from app.reminder_store import ReminderStore


def build_bot(settings: Settings, store: ReminderStore) -> Application:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required when ENABLE_BOT=true")

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["settings"] = settings
    application.bot_data["store"] = store
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("remind", handlers.remind))
    application.add_handler(CommandHandler("list", handlers.list_reminders))
    application.add_handler(CommandHandler("delete", handlers.delete))
    application.add_handler(CommandHandler("pause", handlers.pause))
    application.add_handler(CommandHandler("resume", handlers.resume))
    application.add_handler(CommandHandler("status", handlers.status))
    application.add_handler(CommandHandler("logs", handlers.logs))
    return application

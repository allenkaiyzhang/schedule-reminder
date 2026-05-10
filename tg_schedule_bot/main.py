from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler

from adapters.ops_api_client import OpsApiClient
from config import get_settings
from handlers.telegram_handlers import (
    help_command,
    logs,
    projects,
    pull_notifications,
    start,
    status,
)


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)


def build_application() -> Application:
    settings = get_settings()
    application = Application.builder().token(settings.telegram_bot_token).build()
    application.bot_data["ops_api_client"] = OpsApiClient(
        base_url=settings.ops_core_base_url,
        api_token=settings.ops_api_token,
        timeout_seconds=settings.ops_api_timeout_seconds,
    )
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("projects", projects))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("logs", logs))
    application.add_handler(CommandHandler("pull_notifications", pull_notifications))
    return application


def main() -> None:
    build_application().run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()

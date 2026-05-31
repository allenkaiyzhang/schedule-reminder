from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from telegram.ext import Application

from app.backend import build_backend_client
from app.bot import build_bot
from app.config import get_settings
from app.logging_config import setup_logging
from app.reminder_store import ReminderStore
from app.scheduler import ReminderScheduler


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.log_file)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    store = ReminderStore(settings.sqlite_path)
    backend = build_backend_client(settings)
    app.state.settings = settings
    app.state.store = store
    app.state.backend = backend

    bot_app: Application | None = None
    scheduler: ReminderScheduler | None = None
    if settings.enable_bot:
        bot_app = build_bot(settings, store, backend)
        await bot_app.initialize()
        if bot_app.updater is None:
            raise RuntimeError("Telegram updater is not available")
        await bot_app.updater.start_polling(allowed_updates=["message"])
        await bot_app.start()
        scheduler = ReminderScheduler(
            store=store,
            bot_token=settings.telegram_bot_token,
            timezone_name=settings.timezone,
            disable_send=settings.disable_telegram_send,
            max_instances=settings.scheduler_max_instances,
            coalesce=settings.scheduler_coalesce,
        )
        scheduler.start()
        logger.info("Telegram bot and reminder scheduler started")
    else:
        logger.info("Telegram bot disabled; health endpoint only")

    try:
        yield
    finally:
        if scheduler is not None:
            await scheduler.shutdown()
        if bot_app is not None:
            if bot_app.updater is not None and bot_app.updater.running:
                await bot_app.updater.stop()
            if bot_app.running:
                await bot_app.stop()
            await bot_app.shutdown()


app = FastAPI(title="schedule-reminder", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "schedule-reminder",
        "role": "telegram-adapter",
        "backend_mode": settings.backend_mode,
    }


@app.get("/health/backend")
async def backend_health() -> dict[str, object]:
    settings = get_settings()
    backend = build_backend_client(settings)
    health = await backend.health()
    return {
        "status": health.status,
        "service": "schedule-reminder",
        "role": "telegram-adapter",
        "backend_mode": settings.backend_mode,
        "ops_core_base_url": health.ops_core_base_url,
        "last_success": health.last_success,
        "last_error": health.last_error,
    }

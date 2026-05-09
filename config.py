from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _parse_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        logging.warning("Invalid integer config value, using default %s", default)
        return default


def _parse_int_list(value: str | None) -> list[int]:
    if not value:
        return []

    result: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.append(int(item))
        except ValueError:
            logging.warning("Skipping invalid integer list item in config")
    return result


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    default_timezone: str
    database_path: Path
    check_interval_seconds: int
    default_remind_before_minutes: list[int]
    allowed_user_ids: set[int]


def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    return Settings(
        telegram_bot_token=token,
        default_timezone=os.getenv("DEFAULT_TIMEZONE", "Asia/Singapore").strip()
        or "Asia/Singapore",
        database_path=Path(os.getenv("DATABASE_PATH", "./data/schedule.db")),
        check_interval_seconds=_parse_int(os.getenv("CHECK_INTERVAL_SECONDS"), 30),
        default_remind_before_minutes=_parse_int_list(
            os.getenv("DEFAULT_REMIND_BEFORE_MINUTES", "30,10,0")
        )
        or [30, 10, 0],
        allowed_user_ids=set(_parse_int_list(os.getenv("ALLOWED_USER_IDS"))),
    )

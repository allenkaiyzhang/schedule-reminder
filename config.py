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
        logging.warning("整数配置无效，使用默认值 %s", default)
        return default


def _parse_float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        logging.warning("浮点数配置无效，使用默认值 %s", default)
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
            logging.warning("跳过无效的整数列表配置项")
    return result


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_str_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    default_timezone: str
    database_path: Path
    check_interval_seconds: int
    default_remind_before_minutes: list[int]
    allowed_user_ids: set[int]
    ai_provider: str
    ai_api_key: str
    ai_base_url: str
    ai_model: str
    ai_timeout_seconds: float
    morning_summary_hour: int
    evening_summary_hour: int
    log_dir: Path
    sqlite_busy_timeout_ms: int
    ssh_key_path: Path
    ssh_timeout_seconds: int
    default_log_lines: int
    projects_config_path: Path
    notification_pull_enabled: bool
    notification_pull_interval_seconds: int
    notification_pull_projects: list[str]
    notification_pull_lines: int
    telegram_notify_chat_id: int | None


def get_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 是必填配置")

    provider = os.getenv("AI_PROVIDER", "disabled").strip().lower() or "disabled"
    return Settings(
        telegram_bot_token=token,
        default_timezone=os.getenv(
            "DEFAULT_TIMEZONE", os.getenv("TIMEZONE", "Asia/Singapore")
        ).strip()
        or "Asia/Singapore",
        database_path=Path(os.getenv("DATABASE_PATH", "./data/schedule.db")),
        check_interval_seconds=_parse_int(os.getenv("CHECK_INTERVAL_SECONDS"), 30),
        default_remind_before_minutes=_parse_int_list(
            os.getenv("DEFAULT_REMIND_BEFORE_MINUTES", "30,10,0")
        )
        or [30, 10, 0],
        allowed_user_ids=set(_parse_int_list(os.getenv("ALLOWED_USER_IDS"))),
        ai_provider=provider,
        ai_api_key=os.getenv("AI_API_KEY", "").strip(),
        ai_base_url=os.getenv("AI_BASE_URL", "").strip(),
        ai_model=os.getenv("AI_MODEL", "").strip(),
        ai_timeout_seconds=_parse_float(os.getenv("AI_TIMEOUT_SECONDS"), 20.0),
        morning_summary_hour=_parse_int(os.getenv("MORNING_SUMMARY_HOUR"), 8),
        evening_summary_hour=_parse_int(os.getenv("EVENING_SUMMARY_HOUR"), 22),
        log_dir=Path(os.getenv("LOG_DIR", "./logs")),
        sqlite_busy_timeout_ms=_parse_int(os.getenv("SQLITE_BUSY_TIMEOUT_MS"), 5000),
        ssh_key_path=Path(os.getenv("SSH_KEY_PATH", "/opt/tg_schedule_bot/keys/control_key")),
        ssh_timeout_seconds=_parse_int(os.getenv("SSH_TIMEOUT_SECONDS"), 10),
        default_log_lines=_parse_int(os.getenv("DEFAULT_LOG_LINES"), 80),
        projects_config_path=Path(os.getenv("PROJECTS_CONFIG_PATH", "./projects.yaml")),
        notification_pull_enabled=_parse_bool(
            os.getenv("NOTIFICATION_PULL_ENABLED"), False
        ),
        notification_pull_interval_seconds=_parse_int(
            os.getenv("NOTIFICATION_PULL_INTERVAL_SECONDS"), 120
        ),
        notification_pull_projects=_parse_str_list(
            os.getenv("NOTIFICATION_PULL_PROJECTS", "api-report-agent")
        ),
        notification_pull_lines=_parse_int(os.getenv("NOTIFICATION_PULL_LINES"), 50),
        telegram_notify_chat_id=(
            _parse_int(os.getenv("TELEGRAM_NOTIFY_CHAT_ID"), 0) or None
        ),
    )

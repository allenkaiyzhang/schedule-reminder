from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _int_set_env(name: str) -> set[int]:
    result: set[int] = set()
    for item in os.getenv(name, "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.add(int(item))
        except ValueError:
            continue
    return result


@dataclass(frozen=True)
class Settings:
    ops_api_token: str
    ops_api_host: str
    ops_api_port: int
    allowed_user_ids: set[int]
    ssh_key_path: Path
    ssh_timeout_seconds: int
    default_log_lines: int
    projects_config_path: Path
    database_path: Path
    log_dir: Path
    telegram_bot_token: str
    telegram_notify_chat_id: int | None
    notification_pull_lines: int


def get_settings() -> Settings:
    token = os.getenv("OPS_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("OPS_API_TOKEN is required")

    notify_chat_id = _int_env("TELEGRAM_NOTIFY_CHAT_ID", 0)
    return Settings(
        ops_api_token=token,
        ops_api_host=os.getenv("OPS_API_HOST", "0.0.0.0").strip() or "0.0.0.0",
        ops_api_port=_int_env("OPS_API_PORT", 8080),
        allowed_user_ids=_int_set_env("ALLOWED_USER_IDS"),
        ssh_key_path=Path(os.getenv("SSH_KEY_PATH", "")),
        ssh_timeout_seconds=_int_env("SSH_TIMEOUT_SECONDS", 10),
        default_log_lines=_int_env("DEFAULT_LOG_LINES", 80),
        projects_config_path=Path(os.getenv("PROJECTS_CONFIG_PATH", "./projects.yaml")),
        database_path=Path(os.getenv("DATABASE_PATH", "./data/ops_core.db")),
        log_dir=Path(os.getenv("LOG_DIR", "./logs")),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_notify_chat_id=notify_chat_id or None,
        notification_pull_lines=_int_env("NOTIFICATION_PULL_LINES", 50),
    )

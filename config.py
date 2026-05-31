from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


load_dotenv()


def _parse_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        return int(value)
    except ValueError:
        logging.warning("Invalid integer config; using default %s", default)
        return default


def _parse_float(value: str | None, default: float) -> float:
    if value is None or value.strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        logging.warning("Invalid float config; using default %s", default)
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
            logging.warning("Skipping invalid integer list config item")
    return result


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_str_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _registry_path() -> Path:
    return Path(os.getenv("SCHEDULE_REMINDER_REGISTRY", "registry.yaml"))


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Registry file must contain a YAML mapping: {path}")
    return data


def _registry_value(registry: dict[str, Any], dotted_path: str, default: Any) -> Any:
    current: Any = registry
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def get_registry_bool(dotted_path: str, default: bool = False) -> bool:
    value = _registry_value(_load_registry(), dotted_path, default)
    if isinstance(value, bool):
        return value
    return _parse_bool(str(value), default)


def _registry_str(registry: dict[str, Any], dotted_path: str, default: str) -> str:
    value = _registry_value(registry, dotted_path, default)
    return str(value).strip() or default


def _registry_int(registry: dict[str, Any], dotted_path: str, default: int) -> int:
    value = _registry_value(registry, dotted_path, default)
    return _parse_int(str(value), default)


def _registry_float(registry: dict[str, Any], dotted_path: str, default: float) -> float:
    value = _registry_value(registry, dotted_path, default)
    return _parse_float(str(value), default)


def _registry_int_list(
    registry: dict[str, Any], dotted_path: str, default: list[int]
) -> list[int]:
    value = _registry_value(registry, dotted_path, default)
    if isinstance(value, list):
        result: list[int] = []
        for item in value:
            try:
                result.append(int(item))
            except (TypeError, ValueError):
                logging.warning("Skipping invalid registry integer list item: %s", dotted_path)
        return result or default
    return _parse_int_list(str(value)) or default


def _registry_str_list(
    registry: dict[str, Any], dotted_path: str, default: list[str]
) -> list[str]:
    value = _registry_value(registry, dotted_path, default)
    if isinstance(value, list):
        result = [str(item).strip() for item in value if str(item).strip()]
        return result or default
    return _parse_str_list(str(value)) or default


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
    registry = _load_registry()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    return Settings(
        telegram_bot_token=token,
        default_timezone=_registry_str(
            registry, "service.timezone", "America/Los_Angeles"
        ),
        database_path=Path(
            _registry_str(registry, "storage.database_path", "./data/schedule.db")
        ),
        check_interval_seconds=_registry_int(
            registry, "scheduler.check_interval_seconds", 30
        ),
        default_remind_before_minutes=_registry_int_list(
            registry, "scheduler.default_remind_before_minutes", [30, 10, 0]
        ),
        allowed_user_ids=set(_parse_int_list(os.getenv("ALLOWED_USER_IDS"))),
        ai_provider=_registry_str(registry, "ai.provider", "disabled").lower(),
        ai_api_key=os.getenv("AI_API_KEY", "").strip(),
        ai_base_url=_registry_str(registry, "ai.base_url", ""),
        ai_model=_registry_str(registry, "ai.model", ""),
        ai_timeout_seconds=_registry_float(registry, "ai.timeout_seconds", 20.0),
        morning_summary_hour=_registry_int(
            registry, "scheduler.morning_summary_hour", 8
        ),
        evening_summary_hour=_registry_int(
            registry, "scheduler.evening_summary_hour", 22
        ),
        log_dir=Path(_registry_str(registry, "storage.log_dir", "./logs")),
        sqlite_busy_timeout_ms=_registry_int(
            registry, "storage.sqlite_busy_timeout_ms", 5000
        ),
        ssh_key_path=Path(
            _registry_str(
                registry, "ops.ssh_key_path", "/opt/schedule-reminder/keys/control_key"
            )
        ),
        ssh_timeout_seconds=_registry_int(registry, "ops.ssh_timeout_seconds", 10),
        default_log_lines=_registry_int(registry, "ops.default_log_lines", 80),
        projects_config_path=Path(
            _registry_str(registry, "ops.projects_config_path", "./projects.yaml")
        ),
        notification_pull_enabled=get_registry_bool("notifications.pull_enabled", False),
        notification_pull_interval_seconds=_registry_int(
            registry, "notifications.pull_interval_seconds", 120
        ),
        notification_pull_projects=_registry_str_list(
            registry, "notifications.pull_projects", ["api-report-agent"]
        ),
        notification_pull_lines=_registry_int(registry, "notifications.pull_lines", 50),
        telegram_notify_chat_id=(
            _parse_int(os.getenv("TELEGRAM_NOTIFY_CHAT_ID"), 0) or None
        ),
    )

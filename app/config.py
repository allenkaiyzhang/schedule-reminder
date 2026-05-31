from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _csv_env(name: str) -> set[str]:
    value = os.getenv(name, "").strip()
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def _load_registry() -> dict[str, Any]:
    path = Path(os.getenv("SCHEDULE_REMINDER_REGISTRY", "registry.yaml"))
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        value = yaml.safe_load(file) or {}
    if not isinstance(value, dict):
        raise RuntimeError(f"registry must be a YAML mapping: {path}")
    return value


def _get(registry: dict[str, Any], dotted: str, default: Any) -> Any:
    current: Any = registry
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def _str(registry: dict[str, Any], dotted: str, default: str) -> str:
    return str(_get(registry, dotted, default)).strip() or default


def _int(registry: dict[str, Any], dotted: str, default: int) -> int:
    return int(_get(registry, dotted, default))


def _bool(registry: dict[str, Any], dotted: str, default: bool) -> bool:
    value = _get(registry, dotted, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on", "y"}


@dataclass(frozen=True)
class Settings:
    service_name: str
    host: str
    port: int
    health_path: str
    timezone: str
    data_dir: Path
    log_dir: Path
    sqlite_path: Path
    log_file: Path
    parse_mode: str
    command_timeout_seconds: int
    telegram_bot_token: str
    allowed_user_ids: set[str]
    default_chat_id: str
    admin_bearer_token: str
    ops_core_base_url: str
    ops_core_token: str
    backend_mode: str
    backend_timeout_seconds: float
    backend_interaction_path: str
    backend_health_path: str
    backend_show_mock_banner: bool
    mock_enabled: bool
    mock_allow_demo_actions: bool
    mock_banner: str
    enable_bot: bool
    disable_telegram_send: bool
    scheduler_max_instances: int
    scheduler_coalesce: bool
    install_path: str
    systemd_service: str


def get_settings() -> Settings:
    registry = _load_registry()
    data_dir = Path(_str(registry, "paths.data_dir", "data"))
    log_dir = Path(_str(registry, "paths.log_dir", "logs"))
    return Settings(
        service_name=_str(registry, "service.name", "schedule-reminder"),
        host=_str(registry, "service.host", "127.0.0.1"),
        port=_int(registry, "service.port", 8030),
        health_path=_str(registry, "service.health_path", "/health"),
        timezone=_str(registry, "scheduler.timezone", "Asia/Shanghai"),
        data_dir=data_dir,
        log_dir=log_dir,
        sqlite_path=Path(_str(registry, "paths.sqlite_path", str(data_dir / "reminders.db"))),
        log_file=Path(_str(registry, "paths.log_file", str(log_dir / "schedule-reminder.log"))),
        parse_mode=_str(registry, "telegram.parse_mode", "HTML"),
        command_timeout_seconds=_int(registry, "telegram.command_timeout_seconds", 10),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        allowed_user_ids=_csv_env("ALLOWED_USER_IDS"),
        default_chat_id=os.getenv("DEFAULT_CHAT_ID", "").strip(),
        admin_bearer_token=os.getenv("ADMIN_BEARER_TOKEN", "").strip(),
        ops_core_base_url=os.getenv("OPS_CORE_BASE_URL", "http://127.0.0.1:8080").rstrip("/"),
        ops_core_token=os.getenv("OPS_CORE_TOKEN", "").strip(),
        backend_mode=os.getenv("BACKEND_MODE", _str(registry, "backend.mode", "fallback")).strip().lower(),
        backend_timeout_seconds=float(os.getenv("BACKEND_TIMEOUT_SECONDS", _str(registry, "backend.timeout_seconds", "5"))),
        backend_interaction_path=_str(registry, "backend.interaction_path", "/api/interactions/telegram"),
        backend_health_path=_str(registry, "backend.health_path", "/health"),
        backend_show_mock_banner=_bool(registry, "backend.show_mock_banner", True),
        mock_enabled=_bool(registry, "mock.enabled", True),
        mock_allow_demo_actions=_bool(registry, "mock.allow_demo_actions", True),
        mock_banner=_str(
            registry,
            "mock.banner",
            "MOCK MODE - ops-core business actions are unavailable",
        ),
        enable_bot=_bool_env("ENABLE_BOT", _bool(registry, "telegram.enable_bot", True)),
        disable_telegram_send=_bool_env(
            "DISABLE_TELEGRAM_SEND", _bool(registry, "telegram.disable_send", False)
        ),
        scheduler_max_instances=_int(registry, "scheduler.max_instances", 1),
        scheduler_coalesce=_bool(registry, "scheduler.coalesce", True),
        install_path=_str(registry, "deploy.install_path", "/opt/schedule-reminder"),
        systemd_service=_str(registry, "deploy.systemd_service", "schedule-reminder"),
    )

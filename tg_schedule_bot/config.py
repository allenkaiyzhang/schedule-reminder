from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    ops_core_base_url: str
    ops_api_token: str
    ops_api_timeout_seconds: float


def get_settings() -> Settings:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    api_token = os.getenv("OPS_API_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    if not api_token:
        raise RuntimeError("OPS_API_TOKEN is required")
    return Settings(
        telegram_bot_token=bot_token,
        ops_core_base_url=os.getenv("OPS_CORE_BASE_URL", "http://127.0.0.1:8080").rstrip("/"),
        ops_api_token=api_token,
        ops_api_timeout_seconds=float(os.getenv("OPS_API_TIMEOUT_SECONDS", "15")),
    )

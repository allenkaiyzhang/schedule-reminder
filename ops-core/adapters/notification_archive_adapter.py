from __future__ import annotations

import httpx


class TelegramNotificationAdapter:
    def __init__(self, bot_token: str):
        self.bot_token = bot_token

    def send_message(self, *, chat_id: int, text: str, timeout_seconds: int = 10) -> None:
        if not self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required for notifications")
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(url, json={"chat_id": chat_id, "text": text})
            response.raise_for_status()

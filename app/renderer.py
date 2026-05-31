from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.backend.base import UiResponse


def render_text(response: UiResponse) -> str:
    parts = []
    if response.banner:
        parts.append(response.banner)
    parts.append(f"<b>{response.title}</b>")
    if response.body:
        parts.append(response.body)
    if response.degraded:
        parts.append("Status: degraded. No real business success is being claimed.")
    return "\n\n".join(parts)


def render_markup(response: UiResponse) -> InlineKeyboardMarkup | None:
    if not response.buttons:
        return None
    rows = [
        [InlineKeyboardButton(button.text, callback_data=button.action)]
        for button in response.buttons
    ]
    return InlineKeyboardMarkup(rows)

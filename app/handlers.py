from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.backend import BackendClient
from app.config import Settings
from app.renderer import render_markup, render_text


MAX_LOG_LINES = 200


def _is_allowed(update: Update, settings: Settings) -> bool:
    user = update.effective_user
    return bool(user and str(user.id) in settings.allowed_user_ids)


async def _reject(update: Update, settings: Settings) -> bool:
    if _is_allowed(update, settings):
        return False
    if update.message:
        await update.message.reply_text("This bot is private. Your Telegram user is not allowed.")
    return True


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data["settings"]


def _backend(context: ContextTypes.DEFAULT_TYPE) -> BackendClient:
    return context.application.bot_data["backend"]


async def _send_backend(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    action: str,
    payload: dict,
) -> None:
    settings = _settings(context)
    if await _reject(update, settings):
        return
    response = await _backend(context).handle(action, payload)
    text = render_text(response)
    markup = render_markup(response)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode="HTML")
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode="HTML")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_backend(update, context, "nav:home", _payload(update, context))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_backend(update, context, "mock:demo", _payload(update, context))


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payload = _payload(update, context)
    payload["text"] = " ".join(context.args)
    await _send_backend(update, context, "reminder:create", payload)


async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_backend(update, context, "mock:reminders", _payload(update, context))


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payload = _payload(update, context)
    payload["id"] = _first_arg(context)
    await _send_backend(update, context, "reminder:delete", payload)


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payload = _payload(update, context)
    payload["id"] = _first_arg(context)
    await _send_backend(update, context, "reminder:pause", payload)


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    payload = _payload(update, context)
    payload["id"] = _first_arg(context)
    await _send_backend(update, context, "reminder:resume", payload)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send_backend(update, context, "system:adapter_status", _payload(update, context))


async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = _settings(context)
    if await _reject(update, settings):
        return
    lines = _parse_lines(context.args)
    text = _tail_file(settings.log_file, lines) or "No local log output yet."
    if update.message:
        await update.message.reply_text(text[-3500:])


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query is None:
        return
    action = update.callback_query.data or "mock:home"
    await _send_backend(update, context, action, _payload(update, context))


def _payload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict:
    return {
        "user_id": str(update.effective_user.id) if update.effective_user else "",
        "chat_id": str(update.effective_chat.id) if update.effective_chat else "",
        "request": update.effective_message.text if update.effective_message else "",
        "args": list(context.args),
    }


def _first_arg(context: ContextTypes.DEFAULT_TYPE) -> str | None:
    return context.args[0] if context.args else None


def _parse_lines(args: list[str]) -> int:
    if not args:
        return 80
    try:
        return max(1, min(MAX_LOG_LINES, int(args[0])))
    except ValueError:
        return 80


def _tail_file(path, lines: int) -> str:
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as file:
        content = file.readlines()[-lines:]
    return "".join(content)

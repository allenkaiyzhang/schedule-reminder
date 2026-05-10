from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from audit import write_audit
from auth import is_allowed_user
from config import Settings
from notification_puller import pull_project_notifications


async def pull_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    user = update.effective_user
    message = update.effective_message
    if user is None or not is_allowed_user(user.id, settings):
        await message.reply_text("你没有权限执行通知拉取。")
        return

    if len(context.args) != 1:
        await message.reply_text("用法：/pull_notifications <project>")
        return

    project_name = context.args[0]
    chat_id = (
        settings.telegram_notify_chat_id
        if settings.telegram_notify_chat_id is not None
        else update.effective_chat.id
    )
    result = await pull_project_notifications(
        db=context.application.bot_data["db"],
        bot=context.application.bot,
        settings=settings,
        project_name=project_name,
        chat_id=chat_id,
    )
    write_audit(
        user.id,
        "pull_notifications",
        result.project,
        result.error is None and result.failed == 0,
        0,
        result.error
        or (
            f"fetched={result.fetched} invalid={result.invalid} "
            f"skipped={result.skipped} pushed={result.pushed} failed={result.failed}"
        ),
        log_path=settings.log_dir / "audit.log",
    )
    if result.error:
        await message.reply_text(f"拉取失败：{result.error}")
        return

    await message.reply_text(
        "通知拉取完成\n"
        f"项目：{result.project}\n"
        f"读取：{result.fetched}\n"
        f"推送：{result.pushed}\n"
        f"已跳过：{result.skipped}\n"
        f"无效：{result.invalid}\n"
        f"失败：{result.failed}"
    )

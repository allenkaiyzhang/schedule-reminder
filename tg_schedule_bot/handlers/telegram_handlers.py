from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from adapters.ops_api_client import OpsApiClient


HELP_TEXT = """可用命令：
/projects - 查看可用项目
/status <project> - 查询项目状态
/logs <project> [lines] - 查询项目日志，最多 300 行
/pull_notifications <project> - 拉取并推送项目通知
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text("ops Telegram Adapter 已启动。\n\n" + HELP_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(HELP_TEXT)


async def projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    client = _client(context)
    result = client.get_projects(
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
    )
    if not result.get("ok"):
        await update.effective_message.reply_text(_error_message(result))
        return
    names = result.get("projects") or []
    await update.effective_message.reply_text(
        "可用项目：\n" + "\n".join(f"- {name}" for name in names)
        if names
        else "暂无可用项目。"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.effective_message.reply_text("用法：/status <project>")
        return
    result = _client(context).get_project_status(
        context.args[0],
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
    )
    await update.effective_message.reply_text(_result_message(result))


async def logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) not in {1, 2}:
        await update.effective_message.reply_text("用法：/logs <project> [lines]")
        return
    lines = None
    if len(context.args) == 2:
        try:
            lines = int(context.args[1])
        except ValueError:
            await update.effective_message.reply_text("lines 必须是整数")
            return
    result = _client(context).get_project_logs(
        context.args[0],
        lines,
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
    )
    await update.effective_message.reply_text(_result_message(result))


async def pull_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) != 1:
        await update.effective_message.reply_text("用法：/pull_notifications <project>")
        return
    result = _client(context).pull_notifications(
        context.args[0],
        user_id=update.effective_user.id,
        chat_id=update.effective_chat.id,
    )
    if not result.get("ok"):
        await update.effective_message.reply_text(_error_message(result))
        return
    data = result.get("data") or {}
    await update.effective_message.reply_text(
        "通知拉取完成\n"
        f"项目：{result.get('project')}\n"
        f"推送：{result.get('pushed_count', 0)}\n"
        f"读取：{data.get('fetched', 0)}\n"
        f"跳过：{data.get('skipped', 0)}\n"
        f"无效：{data.get('invalid', 0)}\n"
        f"失败：{data.get('failed', 0)}"
    )


def _client(context: ContextTypes.DEFAULT_TYPE) -> OpsApiClient:
    return context.application.bot_data["ops_api_client"]


def _result_message(result: dict) -> str:
    if not result.get("ok"):
        return _error_message(result)
    return str(result.get("message") or "命令执行完成，但没有输出")


def _error_message(result: dict) -> str:
    return str(result.get("message") or result.get("error") or "请求失败")

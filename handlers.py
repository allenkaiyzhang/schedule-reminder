from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes

from ai.client import AIProvider
from ai.schemas import ParsedAISchedule, ValidationError
from config import Settings
from db import Database, parse_iso, text_to_minutes
from parser import (
    ParseError,
    parse_add_command,
    parse_duration,
    parse_minutes_csv,
    parse_repeat_rule,
    parse_strict_schedule,
    reminder_times,
)
from reminder import format_schedule_time


logger = logging.getLogger(__name__)

HELP_TEXT = """可用命令：
/start - 开始使用
/help - 查看帮助
/add YYYY-MM-DD HH:MM 标题 - 添加日程
/list - 查看待办
/today - 查看今天
/tomorrow - 查看明天
/edit ID title 新标题 - 修改标题
/edit ID time YYYY-MM-DD HH:MM - 修改时间
/edit ID desc 新备注 - 修改备注
/remind ID 60m,30m,10m - 设置提醒时间
/snooze 10m - 延后最近提醒
/repeat ID daily|weekly|monthly - 设置重复
/done ID - 完成任务
/delete ID - 取消任务

也可以直接发送自然语言，例如：
明天下午三点提醒我开会
每周五晚上8点复盘交易
"""


HELP_TEXT = """可用命令：

日程管理：
/start - 开始使用
/help - 查看帮助
/add YYYY-MM-DD HH:MM 标题 - 添加日程
/list - 查看待办
/today - 查看今天
/tomorrow - 查看明天
/edit ID title 新标题 - 修改标题
/edit ID time YYYY-MM-DD HH:MM - 修改时间
/edit ID desc 新备注 - 修改备注
/remind ID 60m,30m,10m - 设置提醒时间
/snooze 10m - 延后最近提醒
/repeat ID daily|weekly|monthly - 设置重复
/done ID - 完成任务
/delete ID - 取消任务

项目控制台：
/projects - 查看可用项目
/status <project> - 查询项目状态
/logs <project> [lines] - 查询项目日志，默认行数由配置决定，最多 300 行

也可以直接发送自然语言，例如：
明天下午三点提醒我开会
每周五晚八点复盘交易
"""


def _is_allowed(settings: Settings, update: Update) -> bool:
    user = update.effective_user
    if not settings.allowed_user_ids:
        return False
    return user is not None and user.id in settings.allowed_user_ids


async def _guard(update: Update, settings: Settings) -> bool:
    if _is_allowed(settings, update):
        return True
    if update.effective_message is not None:
        await update.effective_message.reply_text("你没有权限使用这个机器人。")
    return False


def _deps(context: ContextTypes.DEFAULT_TYPE) -> tuple[Database, Settings, AIProvider]:
    return (
        context.application.bot_data["db"],
        context.application.bot_data["settings"],
        context.application.bot_data["ai_provider"],
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    await update.effective_message.reply_text(
        "你好，我是你的私人 AI 日程助手。提醒由本地调度系统执行，AI 只负责理解和分析。\n\n"
        + HELP_TEXT
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    await update.effective_message.reply_text(HELP_TEXT)


async def add_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if message is None or user is None or chat is None:
        return

    try:
        parsed = parse_add_command(message.text or "", settings.default_timezone)
        schedule_id = _create_schedule_from_values(
            db=db,
            settings=settings,
            user_id=user.id,
            chat_id=chat.id,
            title=parsed.title,
            start_at=parsed.utc_start_at,
            timezone_name=parsed.timezone_name,
            remind_before_minutes=settings.default_remind_before_minutes,
            ai_generated=False,
        )
    except ParseError as exc:
        await message.reply_text(str(exc))
        return
    except sqlite3.Error:
        await message.reply_text("保存日程失败，请稍后再试。")
        return

    await message.reply_text(
        f"已添加日程 #{schedule_id}\n"
        f"时间：{parsed.local_start_at.strftime('%Y-%m-%d %H:%M')}\n"
        f"标题：{parsed.title}"
    )


async def natural_language_schedule(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    db, settings, ai_provider = _deps(context)
    if not await _guard(update, settings):
        return
    message = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    if message is None or user is None or chat is None or not message.text:
        return

    try:
        parsed_ai = await ai_provider.parse_schedule(
            message.text,
            timezone_name=settings.default_timezone,
            now=datetime.now(ZoneInfo(settings.default_timezone)),
        )
        schedule_id = _create_schedule_from_ai(
            db=db,
            user_id=user.id,
            chat_id=chat.id,
            parsed=parsed_ai,
        )
        await message.reply_text(
            f"AI 已解析并添加日程 #{schedule_id}\n"
            f"时间：{parsed_ai.start_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"标题：{parsed_ai.title}\n"
            f"重复：{parsed_ai.repeat_rule or '不重复'}\n"
            f"分类：{parsed_ai.category or '未分类'}"
        )
        return
    except Exception as exc:
        logger.info("AI 解析失败，尝试规则解析：%s", exc)

    try:
        parts = message.text.strip().split(maxsplit=2)
        if len(parts) != 3:
            raise ParseError("无法解析自然语言日程")
        parsed = parse_strict_schedule(
            parts[0], parts[1], parts[2], settings.default_timezone
        )
        schedule_id = _create_schedule_from_values(
            db=db,
            settings=settings,
            user_id=user.id,
            chat_id=chat.id,
            title=parsed.title,
            start_at=parsed.utc_start_at,
            timezone_name=parsed.timezone_name,
            remind_before_minutes=settings.default_remind_before_minutes,
            ai_generated=False,
        )
        await message.reply_text(f"已添加日程 #{schedule_id}：{parsed.title}")
    except Exception:
        await message.reply_text(
            "我没能理解这条日程。你可以使用：/add YYYY-MM-DD HH:MM 标题"
        )


async def list_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    await _send_schedule_list(update, db.list_schedules(user_id=update.effective_user.id))


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    await _send_schedule_list(
        update,
        db.schedules_for_local_day(
            user_id=update.effective_user.id,
            timezone_name=settings.default_timezone,
            include_all_statuses=False,
        ),
    )


async def tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    await _send_schedule_list(
        update,
        db.schedules_for_local_day(
            user_id=update.effective_user.id,
            timezone_name=settings.default_timezone,
            day_offset=1,
            include_all_statuses=False,
        ),
    )


async def edit_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    message = update.effective_message
    if len(context.args) < 3:
        await message.reply_text("用法：/edit ID title|time|desc 新内容")
        return

    schedule_id = _parse_int(context.args[0])
    field = context.args[1].lower()
    value = " ".join(context.args[2:]).strip()
    if schedule_id is None or field not in {"title", "time", "desc"} or not value:
        await message.reply_text("用法：/edit ID title|time|desc 新内容")
        return

    row = db.get_schedule(schedule_id=schedule_id, user_id=update.effective_user.id)
    if row is None or row["status"] != "pending":
        await message.reply_text("没有找到可修改的待办日程。")
        return

    minutes = text_to_minutes(row["reminder_minutes"], settings.default_remind_before_minutes)
    title: str | None = None
    description: str | None = None
    start_at: str | None = None
    timezone_name: str | None = None
    remind_values = _reminder_values(parse_iso(row["start_at"]), minutes)

    try:
        if field == "title":
            title = value
        elif field == "desc":
            description = value
        else:
            parts = value.split(maxsplit=1)
            if len(parts) != 2:
                raise ParseError("时间格式无效，请使用 YYYY-MM-DD HH:MM")
            parsed = parse_strict_schedule(
                parts[0], parts[1], row["title"], row["timezone"]
            )
            start_at = parsed.utc_start_at.isoformat(timespec="seconds")
            timezone_name = parsed.timezone_name
            remind_values = _reminder_values(parsed.utc_start_at, minutes)

        ok = db.update_schedule_fields(
            schedule_id=schedule_id,
            user_id=update.effective_user.id,
            title=title,
            description=description,
            start_at=start_at,
            timezone_name=timezone_name,
            remind_at_values=remind_values,
        )
    except ParseError as exc:
        await message.reply_text(str(exc))
        return
    except sqlite3.Error:
        await message.reply_text("修改失败，请稍后再试。")
        return

    await message.reply_text(f"已修改日程 #{schedule_id}。" if ok else "修改失败。")


async def snooze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    if not context.args:
        await update.effective_message.reply_text("用法：/snooze 10m 或 /snooze 1h")
        return
    try:
        delta = parse_duration(context.args[0])
        new_time = datetime.now(timezone.utc) + delta
        row = db.snooze_nearest_reminder(
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            new_remind_at=new_time.isoformat(timespec="seconds"),
        )
    except (ParseError, sqlite3.Error) as exc:
        await update.effective_message.reply_text(str(exc) if isinstance(exc, ParseError) else "延后失败。")
        return
    if row is None:
        await update.effective_message.reply_text("没有找到可以延后的提醒。")
        return
    await update.effective_message.reply_text(
        f"已延后日程 #{row['schedule_id']} 的最近提醒。"
    )


async def repeat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    if len(context.args) != 2:
        await update.effective_message.reply_text("用法：/repeat ID daily|weekly|monthly")
        return
    schedule_id = _parse_int(context.args[0])
    if schedule_id is None:
        await update.effective_message.reply_text("ID 必须是数字。")
        return
    try:
        rule = parse_repeat_rule(context.args[1])
        ok = db.update_schedule_fields(
            schedule_id=schedule_id,
            user_id=update.effective_user.id,
            repeat_rule=rule,
        )
    except (ParseError, sqlite3.Error) as exc:
        await update.effective_message.reply_text(str(exc) if isinstance(exc, ParseError) else "设置重复失败。")
        return
    await update.effective_message.reply_text(
        f"已设置日程 #{schedule_id} 重复规则：{rule}" if ok else "没有找到可设置的待办日程。"
    )


async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    if len(context.args) != 2:
        await update.effective_message.reply_text("用法：/remind ID 60m,30m,10m")
        return
    schedule_id = _parse_int(context.args[0])
    if schedule_id is None:
        await update.effective_message.reply_text("ID 必须是数字。")
        return
    row = db.get_schedule(schedule_id=schedule_id, user_id=update.effective_user.id)
    if row is None or row["status"] != "pending":
        await update.effective_message.reply_text("没有找到可设置提醒的待办日程。")
        return
    try:
        minutes = parse_minutes_csv(context.args[1])
        ok = db.update_schedule_fields(
            schedule_id=schedule_id,
            user_id=update.effective_user.id,
            reminder_minutes=minutes,
            remind_at_values=_reminder_values(parse_iso(row["start_at"]), minutes),
        )
    except (ParseError, sqlite3.Error) as exc:
        await update.effective_message.reply_text(str(exc) if isinstance(exc, ParseError) else "设置提醒失败。")
        return
    await update.effective_message.reply_text(
        f"已重建日程 #{schedule_id} 的提醒：{','.join(str(item) + 'm' for item in minutes)}"
        if ok
        else "设置失败。"
    )


async def mark_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    schedule_id = _first_int_arg(context)
    if schedule_id is None:
        await update.effective_message.reply_text("用法：/done ID")
        return
    try:
        ok = db.mark_done(schedule_id=schedule_id, user_id=update.effective_user.id)
    except sqlite3.Error:
        await update.effective_message.reply_text("更新日程失败。")
        return
    await update.effective_message.reply_text(
        f"已完成日程 #{schedule_id}。" if ok else "没有找到可完成的待办日程。"
    )


async def delete_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db, settings, _ = _deps(context)
    if not await _guard(update, settings):
        return
    schedule_id = _first_int_arg(context)
    if schedule_id is None:
        await update.effective_message.reply_text("用法：/delete ID")
        return
    try:
        ok = db.cancel_schedule(schedule_id=schedule_id, user_id=update.effective_user.id)
    except sqlite3.Error:
        await update.effective_message.reply_text("取消日程失败。")
        return
    await update.effective_message.reply_text(
        f"已取消日程 #{schedule_id}。" if ok else "没有找到该日程。"
    )


def _create_schedule_from_ai(
    *, db: Database, user_id: int, chat_id: int, parsed: ParsedAISchedule
) -> int:
    start_utc = parsed.start_at.astimezone(timezone.utc)
    remind_values = _reminder_values(start_utc, parsed.remind_before_minutes)
    return db.create_schedule(
        user_id=user_id,
        chat_id=chat_id,
        title=parsed.title,
        start_at=start_utc.isoformat(timespec="seconds"),
        timezone_name=parsed.timezone,
        repeat_rule=parsed.repeat_rule,
        remind_at_values=remind_values,
        reminder_minutes=parsed.remind_before_minutes,
        category=parsed.category,
        priority=parsed.priority,
        ai_generated=True,
    )


def _create_schedule_from_values(
    *,
    db: Database,
    settings: Settings,
    user_id: int,
    chat_id: int,
    title: str,
    start_at: datetime,
    timezone_name: str,
    remind_before_minutes: list[int],
    ai_generated: bool,
) -> int:
    remind_values = _reminder_values(start_at, remind_before_minutes)
    return db.create_schedule(
        user_id=user_id,
        chat_id=chat_id,
        title=title,
        start_at=start_at.astimezone(timezone.utc).isoformat(timespec="seconds"),
        timezone_name=timezone_name,
        remind_at_values=remind_values,
        reminder_minutes=remind_before_minutes,
        ai_generated=ai_generated,
    )


def _reminder_values(start_at_utc: datetime, minutes: list[int]) -> list[str]:
    return [
        item.astimezone(timezone.utc).isoformat(timespec="seconds")
        for item in reminder_times(start_at_utc, minutes)
    ]


def _first_int_arg(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    if not context.args:
        return None
    return _parse_int(context.args[0])


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


async def _send_schedule_list(update: Update, rows: list[Any]) -> None:
    message = update.effective_message
    if not rows:
        await message.reply_text("没有待办日程。")
        return

    lines = ["待办日程："]
    for row in rows:
        when = format_schedule_time(row["start_at"], row["timezone"])
        category = f" | {row['category']}" if row["category"] else ""
        repeat_rule = f" | 重复：{row['repeat_rule']}" if row["repeat_rule"] else ""
        lines.append(f"#{row['id']} | {when} | {row['title']}{category}{repeat_rule}")
    await message.reply_text("\n".join(lines))

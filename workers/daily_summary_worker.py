from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Bot

from ai.analyzer import analyze_user_productivity
from ai.client import AIProvider
from ai.summarizer import schedule_rows_for_ai
from db import Database


logger = logging.getLogger("scheduler")


class DailySummaryWorker:
    def __init__(
        self,
        *,
        db: Database,
        bot: Bot,
        ai_provider: AIProvider,
        timezone_name: str,
    ):
        self.db = db
        self.bot = bot
        self.ai_provider = ai_provider
        self.timezone_name = timezone_name

    async def send_morning_summary(self) -> None:
        for user in self.db.list_known_users():
            try:
                rows = self.db.schedules_for_local_day(
                    user_id=user["user_id"],
                    timezone_name=self.timezone_name,
                    include_all_statuses=True,
                )
                pending = [row for row in rows if row["status"] == "pending"]
                expired = [row for row in rows if row["status"] == "expired"]
                ai_text = await self.ai_provider.summarize_day(
                    "今日计划", schedule_rows_for_ai(rows)
                )
                text = [
                    "早安，今日简报",
                    f"今日待办：{len(pending)} 个",
                    f"逾期任务：{len(expired)} 个",
                    "",
                    ai_text,
                ]
                await self.bot.send_message(chat_id=user["chat_id"], text="\n".join(text))
            except Exception:
                logger.exception("发送早间总结失败 user_id=%s", user["user_id"])

    async def send_evening_summary(self) -> None:
        today = datetime.now(ZoneInfo(self.timezone_name)).date().isoformat()
        for user in self.db.list_known_users():
            try:
                rows = self.db.schedules_for_local_day(
                    user_id=user["user_id"],
                    timezone_name=self.timezone_name,
                    include_all_statuses=True,
                )
                done = [row for row in rows if row["status"] == "done"]
                pending = [row for row in rows if row["status"] == "pending"]
                ai_text = await self.ai_provider.summarize_day(
                    "今日复盘", schedule_rows_for_ai(rows)
                )
                analysis = await analyze_user_productivity(
                    db=self.db,
                    ai_provider=self.ai_provider,
                    user_id=user["user_id"],
                )
                self.db.save_analytics(
                    user_id=user["user_id"],
                    date=today,
                    completion_rate=analysis.completion_rate,
                    productivity_score=analysis.productivity_score,
                    summary=ai_text,
                )
                suggestions = "\n".join(f"- {item}" for item in analysis.suggestions)
                text = [
                    "晚间复盘",
                    f"今日完成：{len(done)} 个",
                    f"未完成：{len(pending)} 个",
                    f"完成率：{analysis.completion_rate:.0%}",
                    f"连续完成天数：{analysis.streak_days}",
                    "",
                    ai_text,
                ]
                if suggestions:
                    text.extend(["", "AI 建议：", suggestions])
                await self.bot.send_message(chat_id=user["chat_id"], text="\n".join(text))
            except Exception:
                logger.exception("发送晚间总结失败 user_id=%s", user["user_id"])

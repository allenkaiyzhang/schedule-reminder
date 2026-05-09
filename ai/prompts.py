from __future__ import annotations

import json
from datetime import datetime


def schedule_parse_prompt(text: str, *, timezone_name: str, now: datetime) -> str:
    return f"""
你是日程解析器，只能输出 JSON，不要输出解释。
当前时间：{now.isoformat()}
默认时区：{timezone_name}

从用户文本中提取日程，输出字段：
title: string
start_at: ISO-8601 datetime，必须带时区或可被 timezone 解释
timezone: string
repeat_rule: daily/weekly/monthly/null
remind_before_minutes: number[]
category: work/study/finance/health/personal/server/trading/null
priority: 0-5

用户文本：{text}
""".strip()


def day_summary_prompt(kind: str, schedules: list[dict]) -> str:
    return f"""
你是私人日程助手。请用中文总结用户的{kind}。
不要虚构数据库里没有的任务。
请给出简短、可执行的建议。

日程 JSON：
{json.dumps(schedules, ensure_ascii=False)}
""".strip()


def productivity_prompt(rows: list[dict]) -> str:
    return f"""
你是生产力分析器，只能输出 JSON，不要输出解释。
根据任务数据生成：
completion_rate: 0-1
productivity_score: 0-1
most_delayed_task_type: string|null
peak_productive_hours: string[]
streak_days: integer
suggestions: string[]

任务 JSON：
{json.dumps(rows, ensure_ascii=False)}
""".strip()

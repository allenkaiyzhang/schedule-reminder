from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


VALID_REPEAT_RULES = {None, "daily", "weekly", "monthly"}
VALID_CATEGORIES = {
    "work",
    "study",
    "finance",
    "health",
    "personal",
    "server",
    "trading",
}


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedAISchedule:
    title: str
    start_at: datetime
    timezone: str
    repeat_rule: str | None
    remind_before_minutes: list[int]
    category: str | None = None
    priority: int = 0


@dataclass(frozen=True)
class ProductivityAnalysis:
    completion_rate: float
    productivity_score: float
    most_delayed_task_type: str | None
    peak_productive_hours: list[str]
    streak_days: int
    suggestions: list[str]


def _load_json(value: str) -> dict[str, Any]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValidationError("AI 返回的不是合法 JSON") from exc
    if not isinstance(data, dict):
        raise ValidationError("AI JSON 必须是对象")
    return data


def validate_schedule_json(value: str | dict[str, Any]) -> ParsedAISchedule:
    data = _load_json(value) if isinstance(value, str) else value
    title = str(data.get("title", "")).strip()
    if not title:
        raise ValidationError("缺少 title")

    timezone_name = str(data.get("timezone", "Asia/Singapore")).strip()
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValidationError("timezone 无效") from exc

    start_at_raw = str(data.get("start_at", "")).strip()
    try:
        start_at = datetime.fromisoformat(start_at_raw)
    except ValueError as exc:
        raise ValidationError("start_at 必须是 ISO 时间") from exc
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=ZoneInfo(timezone_name))

    repeat_rule = data.get("repeat_rule")
    if repeat_rule == "":
        repeat_rule = None
    if repeat_rule not in VALID_REPEAT_RULES:
        raise ValidationError("repeat_rule 仅支持 daily/weekly/monthly/null")

    raw_minutes = data.get("remind_before_minutes", [30, 10, 0])
    if not isinstance(raw_minutes, list):
        raise ValidationError("remind_before_minutes 必须是数组")
    minutes = sorted(
        {max(0, int(item)) for item in raw_minutes if isinstance(item, int | float | str)},
        reverse=True,
    )
    if not minutes:
        minutes = [30, 10, 0]

    category = data.get("category")
    if category == "":
        category = None
    if category is not None and category not in VALID_CATEGORIES:
        category = None

    try:
        priority = int(data.get("priority", 0))
    except (TypeError, ValueError):
        priority = 0

    return ParsedAISchedule(
        title=title,
        start_at=start_at,
        timezone=timezone_name,
        repeat_rule=repeat_rule,
        remind_before_minutes=minutes,
        category=category,
        priority=max(0, min(priority, 5)),
    )


def validate_productivity_json(value: str | dict[str, Any]) -> ProductivityAnalysis:
    data = _load_json(value) if isinstance(value, str) else value

    def bounded_float(key: str, default: float) -> float:
        try:
            return max(0.0, min(1.0, float(data.get(key, default))))
        except (TypeError, ValueError):
            return default

    suggestions = data.get("suggestions", [])
    if not isinstance(suggestions, list):
        suggestions = []

    peak_hours = data.get("peak_productive_hours", [])
    if not isinstance(peak_hours, list):
        peak_hours = []

    try:
        streak_days = max(0, int(data.get("streak_days", 0)))
    except (TypeError, ValueError):
        streak_days = 0

    delayed = data.get("most_delayed_task_type")
    return ProductivityAnalysis(
        completion_rate=bounded_float("completion_rate", 0.0),
        productivity_score=bounded_float("productivity_score", 0.0),
        most_delayed_task_type=str(delayed) if delayed else None,
        peak_productive_hours=[str(item) for item in peak_hours[:5]],
        streak_days=streak_days,
        suggestions=[str(item) for item in suggestions[:8]],
    )

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ADD_FORMAT = "%Y-%m-%d %H:%M"
REPEAT_RULES = {"daily", "weekly", "monthly"}


@dataclass(frozen=True)
class ParsedSchedule:
    title: str
    local_start_at: datetime
    utc_start_at: datetime
    timezone_name: str


class ParseError(ValueError):
    pass


def parse_add_command(text: str, default_timezone: str) -> ParsedSchedule:
    parts = text.strip().split(maxsplit=3)
    if len(parts) < 4:
        raise ParseError("用法：/add YYYY-MM-DD HH:MM 标题")

    _, date_part, time_part, title = parts
    return parse_strict_schedule(date_part, time_part, title, default_timezone)


def parse_strict_schedule(
    date_part: str, time_part: str, title: str, default_timezone: str
) -> ParsedSchedule:
    title = title.strip()
    if not title:
        raise ParseError("标题不能为空")

    try:
        tz = ZoneInfo(default_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ParseError(f"配置的时区无效：{default_timezone}") from exc

    try:
        naive_start = datetime.strptime(f"{date_part} {time_part}", ADD_FORMAT)
    except ValueError as exc:
        raise ParseError("时间格式无效，请使用 YYYY-MM-DD HH:MM") from exc

    local_start = naive_start.replace(tzinfo=tz)
    return ParsedSchedule(
        title=title,
        local_start_at=local_start,
        utc_start_at=local_start.astimezone(timezone.utc),
        timezone_name=default_timezone,
    )


def reminder_times(start_at_utc: datetime, before_minutes: list[int]) -> list[datetime]:
    unique_minutes = sorted({max(0, item) for item in before_minutes}, reverse=True)
    return [start_at_utc - timedelta(minutes=minutes) for minutes in unique_minutes]


def parse_duration(value: str) -> timedelta:
    match = re.fullmatch(r"\s*(\d+)\s*([mh])\s*", value, flags=re.IGNORECASE)
    if not match:
        raise ParseError("时长格式无效，请使用 10m 或 1h")
    amount = int(match.group(1))
    unit = match.group(2).lower()
    if amount <= 0:
        raise ParseError("时长必须大于 0")
    return timedelta(minutes=amount) if unit == "m" else timedelta(hours=amount)


def parse_minutes_csv(value: str) -> list[int]:
    result: list[int] = []
    for item in value.split(","):
        item = item.strip().lower()
        if not item:
            continue
        if item.endswith("m"):
            item = item[:-1]
        try:
            minutes = int(item)
        except ValueError as exc:
            raise ParseError("提醒规则格式无效，例如：60m,30m,10m") from exc
        if minutes < 0:
            raise ParseError("提醒分钟数不能小于 0")
        result.append(minutes)
    if not result:
        raise ParseError("提醒规则不能为空")
    return sorted(set(result), reverse=True)


def parse_repeat_rule(value: str) -> str:
    rule = value.strip().lower()
    if rule not in REPEAT_RULES:
        raise ParseError("重复规则仅支持 daily、weekly、monthly")
    return rule

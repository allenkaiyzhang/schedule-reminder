from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


ADD_FORMAT = "%Y-%m-%d %H:%M"


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
        raise ParseError("Usage: /add YYYY-MM-DD HH:MM title")

    _, date_part, time_part, title = parts
    title = title.strip()
    if not title:
        raise ParseError("Title cannot be empty")

    try:
        tz = ZoneInfo(default_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ParseError(f"Invalid timezone configured: {default_timezone}") from exc

    try:
        naive_start = datetime.strptime(f"{date_part} {time_part}", ADD_FORMAT)
    except ValueError as exc:
        raise ParseError("Invalid datetime. Use YYYY-MM-DD HH:MM") from exc

    local_start = naive_start.replace(tzinfo=tz)
    return ParsedSchedule(
        title=title,
        local_start_at=local_start,
        utc_start_at=local_start.astimezone(timezone.utc),
        timezone_name=default_timezone,
    )


def reminder_times(start_at_utc: datetime, before_minutes: list[int]) -> list[datetime]:
    unique_minutes = sorted(set(before_minutes), reverse=True)
    return [start_at_utc - timedelta(minutes=minutes) for minutes in unique_minutes]

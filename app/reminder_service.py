from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


USAGE = (
    "Usage:\n"
    "/remind 2026-06-01 09:30 Take medicine\n"
    "/remind 2026-06-01 09:30 Asia/Shanghai Take medicine\n"
    "/remind in 10m Take a break\n"
    "/remind in 2h Check report"
)


@dataclass(frozen=True)
class ParsedReminder:
    remind_at: datetime
    timezone_name: str
    text: str


def parse_reminder(text: str, default_timezone: str, now: datetime | None = None) -> ParsedReminder:
    value = text.strip()
    if not value:
        raise ValueError(USAGE)

    current = now or datetime.now(timezone.utc)
    relative = re.match(r"^in\s+(\d+)([mh])\s+(.+)$", value, flags=re.IGNORECASE)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2).lower()
        message = relative.group(3).strip()
        if not message:
            raise ValueError(USAGE)
        delta = timedelta(minutes=amount) if unit == "m" else timedelta(hours=amount)
        return ParsedReminder(
            remind_at=(current + delta).astimezone(timezone.utc),
            timezone_name=default_timezone,
            text=message,
        )

    parts = value.split(maxsplit=3)
    if len(parts) < 3:
        raise ValueError(USAGE)

    date_part, time_part = parts[0], parts[1]
    remainder = parts[2] if len(parts) == 3 else f"{parts[2]} {parts[3]}"
    timezone_name = default_timezone
    message = remainder
    rem_parts = remainder.split(maxsplit=1)
    if len(rem_parts) == 2 and _valid_timezone(rem_parts[0]):
        timezone_name = rem_parts[0]
        message = rem_parts[1].strip()
    if not message:
        raise ValueError(USAGE)

    try:
        local = datetime.strptime(f"{date_part} {time_part}", "%Y-%m-%d %H:%M")
        tz = ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError(USAGE) from exc

    return ParsedReminder(
        remind_at=local.replace(tzinfo=tz).astimezone(timezone.utc),
        timezone_name=timezone_name,
        text=message,
    )


def format_reminder_time(remind_at: str, timezone_name: str) -> str:
    try:
        when = datetime.fromisoformat(remind_at).astimezone(ZoneInfo(timezone_name))
    except (ValueError, ZoneInfoNotFoundError):
        when = datetime.fromisoformat(remind_at).astimezone(timezone.utc)
    return when.strftime("%Y-%m-%d %H:%M %Z")


def _valid_timezone(value: str) -> bool:
    if "/" not in value:
        return False
    try:
        ZoneInfo(value)
        return True
    except ZoneInfoNotFoundError:
        return False

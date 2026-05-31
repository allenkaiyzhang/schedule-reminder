from datetime import datetime, timezone

from app.reminder_service import parse_reminder


def test_parse_absolute_datetime_default_timezone() -> None:
    parsed = parse_reminder(
        "2026-06-01 09:30 Take medicine",
        "Asia/Shanghai",
    )

    assert parsed.text == "Take medicine"
    assert parsed.timezone_name == "Asia/Shanghai"
    assert parsed.remind_at.isoformat() == "2026-06-01T01:30:00+00:00"


def test_parse_absolute_datetime_explicit_timezone() -> None:
    parsed = parse_reminder(
        "2026-06-01 09:30 America/Los_Angeles Take medicine",
        "Asia/Shanghai",
    )

    assert parsed.text == "Take medicine"
    assert parsed.timezone_name == "America/Los_Angeles"


def test_parse_relative_minutes_and_hours() -> None:
    now = datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc)

    minutes = parse_reminder("in 10m Take a break", "Asia/Shanghai", now=now)
    hours = parse_reminder("in 2h Check report", "Asia/Shanghai", now=now)

    assert minutes.remind_at.isoformat() == "2026-06-01T00:10:00+00:00"
    assert hours.remind_at.isoformat() == "2026-06-01T02:00:00+00:00"

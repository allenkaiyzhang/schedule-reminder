from __future__ import annotations

from typing import Any

from ai.client import AIProvider
from db import Database
from reminder import format_schedule_time


def schedule_rows_for_ai(rows) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "title": row["title"],
                "description": row["description"],
                "start_at": row["start_at"],
                "local_time": format_schedule_time(row["start_at"], row["timezone"]),
                "status": row["status"],
                "category": row["category"],
                "priority": row["priority"],
            }
        )
    return result


async def summarize_day(
    *,
    db: Database,
    ai_provider: AIProvider,
    user_id: int,
    timezone_name: str,
    kind: str,
) -> str:
    rows = db.schedules_for_local_day(
        user_id=user_id,
        timezone_name=timezone_name,
        include_all_statuses=True,
    )
    return await ai_provider.summarize_day(kind, schedule_rows_for_ai(rows))

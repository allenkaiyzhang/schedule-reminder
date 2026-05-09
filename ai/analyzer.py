from __future__ import annotations

from datetime import timedelta
from typing import Any

from ai.client import AIProvider
from ai.schemas import ProductivityAnalysis
from db import Database, parse_iso, utc_now


def row_to_dict(row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


async def analyze_user_productivity(
    *, db: Database, ai_provider: AIProvider, user_id: int
) -> ProductivityAnalysis:
    since = (utc_now() - timedelta(days=30)).isoformat(timespec="seconds")
    rows = [row_to_dict(row) for row in db.productivity_source_rows(user_id=user_id, since_iso=since)]
    if not rows:
        return await ai_provider.analyze_productivity([])

    completed = [row for row in rows if row["status"] == "done"]
    completion_rate = len(completed) / max(1, len(rows))
    analysis = await ai_provider.analyze_productivity(rows)
    return ProductivityAnalysis(
        completion_rate=completion_rate,
        productivity_score=analysis.productivity_score,
        most_delayed_task_type=analysis.most_delayed_task_type,
        peak_productive_hours=analysis.peak_productive_hours,
        streak_days=analysis.streak_days,
        suggestions=analysis.suggestions,
    )

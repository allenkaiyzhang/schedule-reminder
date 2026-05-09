from __future__ import annotations

import os

from config import Settings


def is_allowed_user(user_id: int, settings: Settings | None = None) -> bool:
    if settings is not None:
        allowed_user_ids = settings.allowed_user_ids
    else:
        allowed_user_ids = _allowed_user_ids_from_env()
    if not allowed_user_ids:
        return False
    return user_id in allowed_user_ids


def _allowed_user_ids_from_env() -> set[int]:
    result: set[int] = set()
    for item in os.getenv("ALLOWED_USER_IDS", "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.add(int(item))
        except ValueError:
            continue
    return result

from __future__ import annotations

import logging
from datetime import timedelta

from db import Database, utc_now


logger = logging.getLogger("scheduler")


class CleanupWorker:
    def __init__(self, *, db: Database):
        self.db = db

    async def run(self) -> None:
        threshold = (utc_now() - timedelta(hours=24)).isoformat(timespec="seconds")
        expired = self.db.expire_overdue_schedules(older_than_iso=threshold)
        if expired:
            logger.info("已标记过期任务数量=%s", expired)

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class SQLiteAdapter:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS pushed_notifications (
                    id TEXT PRIMARY KEY,
                    project TEXT NOT NULL,
                    level TEXT,
                    title TEXT,
                    time_value TEXT,
                    pushed_at TEXT NOT NULL
                );
                """
            )
            conn.commit()

    def is_notification_pushed(self, notification_id: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM pushed_notifications WHERE id = ?",
                (notification_id,),
            ).fetchone()
            return row is not None

    def mark_notification_pushed(
        self,
        *,
        notification_id: str,
        project: str,
        level: str | None,
        title: str | None,
        time_value: str | None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO pushed_notifications (
                    id, project, level, title, time_value, pushed_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    notification_id,
                    project,
                    level,
                    title,
                    time_value,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            conn.commit()

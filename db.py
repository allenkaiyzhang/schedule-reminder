from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_at TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    repeat_rule TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_id INTEGER NOT NULL,
                    remind_at TEXT NOT NULL,
                    sent_at TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_schedules_user_status_start
                    ON schedules(user_id, status, start_at);

                CREATE INDEX IF NOT EXISTS idx_reminders_status_time
                    ON reminders(status, remind_at);
                """
            )
            conn.commit()

    def create_schedule(
        self,
        *,
        user_id: int,
        chat_id: int,
        title: str,
        start_at: str,
        timezone_name: str,
        remind_at_values: list[str],
        description: str | None = None,
        repeat_rule: str | None = None,
    ) -> int:
        now = utc_now_iso()
        try:
            with self.connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO schedules (
                        user_id, chat_id, title, description, start_at, timezone,
                        status, repeat_rule, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                    """,
                    (
                        user_id,
                        chat_id,
                        title,
                        description,
                        start_at,
                        timezone_name,
                        repeat_rule,
                        now,
                        now,
                    ),
                )
                schedule_id = int(cursor.lastrowid)
                conn.executemany(
                    """
                    INSERT INTO reminders (schedule_id, remind_at, status)
                    VALUES (?, ?, 'pending')
                    """,
                    [(schedule_id, value) for value in remind_at_values],
                )
                conn.commit()
                return schedule_id
        except sqlite3.Error:
            logger.exception("Failed to create schedule")
            raise

    def list_schedules(
        self,
        *,
        user_id: int,
        start_from: str | None = None,
        start_to: str | None = None,
        include_done: bool = False,
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM schedules WHERE user_id = ? AND status != 'deleted'"
        params: list[Any] = [user_id]
        if not include_done:
            sql += " AND status = 'pending'"
        if start_from is not None:
            sql += " AND start_at >= ?"
            params.append(start_from)
        if start_to is not None:
            sql += " AND start_at < ?"
            params.append(start_to)
        sql += " ORDER BY start_at ASC, id ASC"

        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()

    def mark_done(self, *, schedule_id: int, user_id: int) -> bool:
        return self._update_schedule_status(
            schedule_id=schedule_id,
            user_id=user_id,
            from_status="pending",
            to_status="done",
        )

    def delete_schedule(self, *, schedule_id: int, user_id: int) -> bool:
        return self._update_schedule_status(
            schedule_id=schedule_id,
            user_id=user_id,
            from_status=None,
            to_status="deleted",
        )

    def _update_schedule_status(
        self,
        *,
        schedule_id: int,
        user_id: int,
        from_status: str | None,
        to_status: str,
    ) -> bool:
        now = utc_now_iso()
        try:
            with self.connect() as conn:
                sql = """
                    UPDATE schedules
                    SET status = ?, updated_at = ?
                    WHERE id = ? AND user_id = ? AND status != 'deleted'
                """
                params: list[Any] = [to_status, now, schedule_id, user_id]
                if from_status is not None:
                    sql += " AND status = ?"
                    params.append(from_status)
                cursor = conn.execute(sql, params)
                if cursor.rowcount:
                    conn.execute(
                        """
                        UPDATE reminders
                        SET status = 'cancelled'
                        WHERE schedule_id = ? AND status = 'pending'
                        """,
                        (schedule_id,),
                    )
                conn.commit()
                return cursor.rowcount > 0
        except sqlite3.Error:
            logger.exception("Failed to update schedule status")
            raise

    def due_reminders(self, *, now_iso: str, limit: int = 100) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT
                    r.id AS reminder_id,
                    r.remind_at,
                    s.id AS schedule_id,
                    s.user_id,
                    s.chat_id,
                    s.title,
                    s.start_at,
                    s.timezone,
                    s.status AS schedule_status
                FROM reminders r
                JOIN schedules s ON s.id = r.schedule_id
                WHERE r.status = 'pending'
                  AND r.remind_at <= ?
                  AND s.status = 'pending'
                ORDER BY r.remind_at ASC, r.id ASC
                LIMIT ?
                """,
                (now_iso, limit),
            ).fetchall()

    def mark_reminder_sent(self, reminder_id: int) -> None:
        try:
            with self.connect() as conn:
                conn.execute(
                    """
                    UPDATE reminders
                    SET status = 'sent', sent_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (utc_now_iso(), reminder_id),
                )
                conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to mark reminder as sent")
            raise

    def cancel_orphan_pending_reminders(self) -> int:
        try:
            with self.connect() as conn:
                cursor = conn.execute(
                    """
                    UPDATE reminders
                    SET status = 'cancelled'
                    WHERE status = 'pending'
                      AND schedule_id IN (
                        SELECT id FROM schedules WHERE status IN ('done', 'deleted')
                      )
                    """
                )
                conn.commit()
                return cursor.rowcount
        except sqlite3.Error:
            logger.exception("Failed to cancel reminders")
            raise

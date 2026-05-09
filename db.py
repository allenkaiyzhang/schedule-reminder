from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)
T = TypeVar("T")

ACTIVE_STATUSES = {"pending"}
TERMINAL_STATUSES = {"done", "cancelled", "expired"}
REPEAT_RULES = {"daily", "weekly", "monthly"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def minutes_to_text(minutes: list[int]) -> str:
    return ",".join(str(item) for item in sorted(set(minutes), reverse=True))


def text_to_minutes(value: str | None, fallback: list[int]) -> list[int]:
    if not value:
        return fallback
    result: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.append(max(0, int(item)))
        except ValueError:
            continue
    return sorted(set(result), reverse=True) or fallback


class Database:
    def __init__(self, path: Path | str, *, busy_timeout_ms: int = 5000):
        self.path = Path(path)
        self.busy_timeout_ms = busy_timeout_ms
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(
            self.path,
            timeout=self.busy_timeout_ms / 1000,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()

    def _retry(self, operation: Callable[[], T], *, action: str) -> T:
        last_error: sqlite3.OperationalError | None = None
        for attempt in range(4):
            try:
                return operation()
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                last_error = exc
                time.sleep(0.15 * (attempt + 1))
        logger.exception("SQLite lock retry exhausted during %s", action)
        raise last_error or sqlite3.OperationalError("SQLite operation failed")

    def init_db(self) -> None:
        def op() -> None:
            with self.connect() as conn:
                conn.execute("BEGIN")
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

                    CREATE TABLE IF NOT EXISTS analytics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        date TEXT,
                        completion_rate REAL,
                        productivity_score REAL,
                        summary TEXT,
                        created_at TEXT
                    );
                    """
                )
                self._ensure_column(conn, "schedules", "category", "TEXT")
                self._ensure_column(conn, "schedules", "priority", "INTEGER DEFAULT 0")
                self._ensure_column(
                    conn, "schedules", "ai_generated", "INTEGER NOT NULL DEFAULT 0"
                )
                self._ensure_column(conn, "schedules", "completed_at", "TEXT")
                self._ensure_column(conn, "schedules", "reminder_minutes", "TEXT")
                self._ensure_column(conn, "schedules", "recurrence_generated_at", "TEXT")
                self._ensure_column(conn, "schedules", "source_schedule_id", "INTEGER")
                conn.execute(
                    "UPDATE schedules SET status = 'cancelled' WHERE status = 'deleted'"
                )
                conn.executescript(
                    """
                    CREATE INDEX IF NOT EXISTS idx_schedules_user_status_start
                        ON schedules(user_id, status, start_at);

                    CREATE INDEX IF NOT EXISTS idx_schedules_status_repeat
                        ON schedules(status, repeat_rule, recurrence_generated_at);

                    CREATE INDEX IF NOT EXISTS idx_reminders_status_time
                        ON reminders(status, remind_at);

                    DROP INDEX IF EXISTS idx_reminders_unique_pending;

                    CREATE UNIQUE INDEX IF NOT EXISTS idx_reminders_unique_pending
                        ON reminders(schedule_id, remind_at)
                        WHERE status = 'pending';
                    """
                )
                conn.commit()

        self._retry(op, action="init_db")

    @staticmethod
    def _ensure_column(
        conn: sqlite3.Connection, table: str, column: str, definition: str
    ) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def create_schedule(
        self,
        *,
        user_id: int,
        chat_id: int,
        title: str,
        start_at: str,
        timezone_name: str,
        remind_at_values: list[str],
        reminder_minutes: list[int],
        description: str | None = None,
        repeat_rule: str | None = None,
        category: str | None = None,
        priority: int = 0,
        ai_generated: bool = False,
        source_schedule_id: int | None = None,
    ) -> int:
        now = utc_now_iso()

        def op() -> int:
            with self.connect() as conn:
                conn.execute("BEGIN")
                cursor = conn.execute(
                    """
                    INSERT INTO schedules (
                        user_id, chat_id, title, description, start_at, timezone,
                        status, repeat_rule, created_at, updated_at, category, priority,
                        ai_generated, reminder_minutes, source_schedule_id
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?)
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
                        category,
                        priority,
                        1 if ai_generated else 0,
                        minutes_to_text(reminder_minutes),
                        source_schedule_id,
                    ),
                )
                schedule_id = int(cursor.lastrowid)
                self._insert_reminders(conn, schedule_id, remind_at_values)
                conn.commit()
                return schedule_id

        try:
            return self._retry(op, action="create_schedule")
        except sqlite3.Error:
            logger.exception("Failed to create schedule")
            raise

    def _insert_reminders(
        self, conn: sqlite3.Connection, schedule_id: int, remind_at_values: list[str]
    ) -> None:
        conn.executemany(
            """
            INSERT OR IGNORE INTO reminders (schedule_id, remind_at, status)
            VALUES (?, ?, 'pending')
            """,
            [(schedule_id, value) for value in sorted(set(remind_at_values))],
        )

    def get_schedule(self, *, schedule_id: int, user_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM schedules
                WHERE id = ? AND user_id = ? AND status != 'cancelled'
                """,
                (schedule_id, user_id),
            ).fetchone()

    def get_schedule_by_id(self, schedule_id: int) -> sqlite3.Row | None:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM schedules WHERE id = ?",
                (schedule_id,),
            ).fetchone()

    def list_schedules(
        self,
        *,
        user_id: int,
        start_from: str | None = None,
        start_to: str | None = None,
        statuses: list[str] | None = None,
        include_done: bool = False,
    ) -> list[sqlite3.Row]:
        sql = "SELECT * FROM schedules WHERE user_id = ? AND status != 'cancelled'"
        params: list[Any] = [user_id]
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            sql += f" AND status IN ({placeholders})"
            params.extend(statuses)
        elif not include_done:
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

    def list_known_users(self) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT user_id, MAX(chat_id) AS chat_id
                FROM schedules
                WHERE status != 'cancelled'
                GROUP BY user_id
                """
            ).fetchall()

    def update_schedule_fields(
        self,
        *,
        schedule_id: int,
        user_id: int,
        title: str | None = None,
        description: str | None = None,
        start_at: str | None = None,
        timezone_name: str | None = None,
        repeat_rule: str | None = None,
        category: str | None = None,
        priority: int | None = None,
        reminder_minutes: list[int] | None = None,
        remind_at_values: list[str] | None = None,
    ) -> bool:
        updates: list[str] = ["updated_at = ?"]
        params: list[Any] = [utc_now_iso()]
        field_values = {
            "title": title,
            "description": description,
            "start_at": start_at,
            "timezone": timezone_name,
            "repeat_rule": repeat_rule,
            "category": category,
            "priority": priority,
            "reminder_minutes": minutes_to_text(reminder_minutes)
            if reminder_minutes is not None
            else None,
        }
        for field, value in field_values.items():
            if value is not None:
                updates.append(f"{field} = ?")
                params.append(value)
        params.extend([schedule_id, user_id])

        def op() -> bool:
            with self.connect() as conn:
                conn.execute("BEGIN")
                cursor = conn.execute(
                    f"""
                    UPDATE schedules
                    SET {", ".join(updates)}
                    WHERE id = ? AND user_id = ? AND status = 'pending'
                    """,
                    params,
                )
                if cursor.rowcount and remind_at_values is not None:
                    conn.execute(
                        """
                        UPDATE reminders
                        SET status = 'cancelled'
                        WHERE schedule_id = ? AND status = 'pending'
                        """,
                        (schedule_id,),
                    )
                    self._insert_reminders(conn, schedule_id, remind_at_values)
                conn.commit()
                return cursor.rowcount > 0

        try:
            return self._retry(op, action="update_schedule_fields")
        except sqlite3.Error:
            logger.exception("Failed to update schedule")
            raise

    def mark_done(self, *, schedule_id: int, user_id: int) -> bool:
        now = utc_now_iso()

        def op() -> bool:
            with self.connect() as conn:
                conn.execute("BEGIN")
                cursor = conn.execute(
                    """
                    UPDATE schedules
                    SET status = 'done', completed_at = ?, updated_at = ?
                    WHERE id = ? AND user_id = ? AND status = 'pending'
                    """,
                    (now, now, schedule_id, user_id),
                )
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

        try:
            return self._retry(op, action="mark_done")
        except sqlite3.Error:
            logger.exception("Failed to mark schedule done")
            raise

    def cancel_schedule(self, *, schedule_id: int, user_id: int) -> bool:
        return self._update_schedule_status(
            schedule_id=schedule_id,
            user_id=user_id,
            to_status="cancelled",
            from_status=None,
        )

    def _update_schedule_status(
        self,
        *,
        schedule_id: int,
        user_id: int,
        to_status: str,
        from_status: str | None,
    ) -> bool:
        now = utc_now_iso()

        def op() -> bool:
            with self.connect() as conn:
                conn.execute("BEGIN")
                sql = """
                    UPDATE schedules
                    SET status = ?, updated_at = ?
                    WHERE id = ? AND user_id = ? AND status != 'cancelled'
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

        try:
            return self._retry(op, action="update_schedule_status")
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
                    s.description,
                    s.start_at,
                    s.timezone,
                    s.category,
                    s.priority,
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
        def op() -> None:
            with self.connect() as conn:
                conn.execute("BEGIN")
                conn.execute(
                    """
                    UPDATE reminders
                    SET status = 'sent', sent_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (utc_now_iso(), reminder_id),
                )
                conn.commit()

        try:
            self._retry(op, action="mark_reminder_sent")
        except sqlite3.Error:
            logger.exception("Failed to mark reminder as sent")
            raise

    def snooze_nearest_reminder(
        self, *, user_id: int, chat_id: int, new_remind_at: str
    ) -> sqlite3.Row | None:
        def op() -> sqlite3.Row | None:
            with self.connect() as conn:
                conn.execute("BEGIN")
                row = conn.execute(
                    """
                    SELECT r.id AS reminder_id, s.id AS schedule_id, s.title, s.start_at, s.timezone
                    FROM reminders r
                    JOIN schedules s ON s.id = r.schedule_id
                    WHERE s.user_id = ? AND s.chat_id = ?
                      AND s.status = 'pending'
                      AND r.status = 'pending'
                    ORDER BY r.remind_at ASC, r.id ASC
                    LIMIT 1
                    """,
                    (user_id, chat_id),
                ).fetchone()
                if row is not None:
                    conn.execute(
                        "UPDATE reminders SET remind_at = ? WHERE id = ?",
                        (new_remind_at, row["reminder_id"]),
                    )
                    conn.commit()
                    return row

                row = conn.execute(
                    """
                    SELECT r.id AS reminder_id, s.id AS schedule_id, s.title, s.start_at, s.timezone
                    FROM reminders r
                    JOIN schedules s ON s.id = r.schedule_id
                    WHERE s.user_id = ? AND s.chat_id = ?
                      AND s.status = 'pending'
                      AND r.status = 'sent'
                    ORDER BY r.sent_at DESC, r.id DESC
                    LIMIT 1
                    """,
                    (user_id, chat_id),
                ).fetchone()
                if row is not None:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO reminders (schedule_id, remind_at, status)
                        VALUES (?, ?, 'pending')
                        """,
                        (row["schedule_id"], new_remind_at),
                    )
                conn.commit()
                return row

        try:
            return self._retry(op, action="snooze_nearest_reminder")
        except sqlite3.Error:
            logger.exception("Failed to snooze reminder")
            raise

    def cancel_orphan_pending_reminders(self) -> int:
        def op() -> int:
            with self.connect() as conn:
                conn.execute("BEGIN")
                cursor = conn.execute(
                    """
                    UPDATE reminders
                    SET status = 'cancelled'
                    WHERE status = 'pending'
                      AND schedule_id IN (
                        SELECT id FROM schedules
                        WHERE status IN ('done', 'cancelled', 'expired')
                      )
                    """
                )
                conn.commit()
                return cursor.rowcount

        try:
            return self._retry(op, action="cancel_orphan_pending_reminders")
        except sqlite3.Error:
            logger.exception("Failed to cancel reminders")
            raise

    def expire_overdue_schedules(self, *, older_than_iso: str) -> int:
        now = utc_now_iso()

        def op() -> int:
            with self.connect() as conn:
                conn.execute("BEGIN")
                cursor = conn.execute(
                    """
                    UPDATE schedules
                    SET status = 'expired', updated_at = ?
                    WHERE status = 'pending' AND start_at < ?
                    """,
                    (now, older_than_iso),
                )
                conn.execute(
                    """
                    UPDATE reminders
                    SET status = 'cancelled'
                    WHERE status = 'pending'
                      AND schedule_id IN (
                        SELECT id FROM schedules WHERE status = 'expired'
                      )
                    """
                )
                conn.commit()
                return cursor.rowcount

        return self._retry(op, action="expire_overdue_schedules")

    def recurring_done_schedules(self, *, limit: int = 50) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM schedules
                WHERE status = 'done'
                  AND repeat_rule IN ('daily', 'weekly', 'monthly')
                  AND recurrence_generated_at IS NULL
                ORDER BY completed_at ASC, id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def mark_recurrence_generated(self, schedule_id: int) -> None:
        now = utc_now_iso()

        def op() -> None:
            with self.connect() as conn:
                conn.execute("BEGIN")
                conn.execute(
                    """
                    UPDATE schedules
                    SET recurrence_generated_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (now, now, schedule_id),
                )
                conn.commit()

        self._retry(op, action="mark_recurrence_generated")

    def save_analytics(
        self,
        *,
        user_id: int,
        date: str,
        completion_rate: float,
        productivity_score: float,
        summary: str,
    ) -> None:
        now = utc_now_iso()

        def op() -> None:
            with self.connect() as conn:
                conn.execute("BEGIN")
                conn.execute(
                    """
                    INSERT INTO analytics (
                        user_id, date, completion_rate, productivity_score, summary, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, date, completion_rate, productivity_score, summary, now),
                )
                conn.commit()

        self._retry(op, action="save_analytics")

    def schedules_for_local_day(
        self,
        *,
        user_id: int,
        timezone_name: str,
        day_offset: int = 0,
        include_all_statuses: bool = True,
    ) -> list[sqlite3.Row]:
        tz = ZoneInfo(timezone_name)
        local_date = datetime.now(tz).date() + timedelta(days=day_offset)
        start = datetime.combine(local_date, datetime.min.time(), tzinfo=tz)
        end = start + timedelta(days=1)
        statuses = None if include_all_statuses else ["pending"]
        return self.list_schedules(
            user_id=user_id,
            start_from=start.astimezone(timezone.utc).isoformat(timespec="seconds"),
            start_to=end.astimezone(timezone.utc).isoformat(timespec="seconds"),
            statuses=statuses,
            include_done=include_all_statuses,
        )

    def productivity_source_rows(
        self, *, user_id: int, since_iso: str
    ) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM schedules
                WHERE user_id = ?
                  AND status != 'cancelled'
                  AND start_at >= ?
                ORDER BY start_at ASC
                """,
                (user_id, since_iso),
            ).fetchall()

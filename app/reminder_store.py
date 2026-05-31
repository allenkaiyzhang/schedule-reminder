from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


STATUSES = {"active", "paused", "sent", "deleted", "failed"}


@dataclass(frozen=True)
class Reminder:
    id: int
    user_id: str
    chat_id: str
    text: str
    remind_at: str
    timezone: str
    status: str
    created_at: str
    updated_at: str
    sent_at: str | None


class ReminderStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    chat_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    timezone TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    sent_at TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(status, remind_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminders_user ON reminders(user_id, status)"
            )

    def create(
        self, *, user_id: str, chat_id: str, text: str, remind_at: str, timezone_name: str
    ) -> Reminder:
        now = _now_iso()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reminders (
                    user_id, chat_id, text, remind_at, timezone, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (user_id, chat_id, text, remind_at, timezone_name, now, now),
            )
            reminder_id = int(cursor.lastrowid)
        reminder = self.get(reminder_id)
        if reminder is None:
            raise RuntimeError("created reminder could not be loaded")
        return reminder

    def get(self, reminder_id: int) -> Reminder | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
        return _row_to_reminder(row) if row else None

    def list_for_user(self, user_id: str) -> list[Reminder]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM reminders
                WHERE user_id = ? AND status IN ('active', 'paused')
                ORDER BY remind_at ASC, id ASC
                """,
                (user_id,),
            ).fetchall()
        return [_row_to_reminder(row) for row in rows]

    def set_status_for_user(self, reminder_id: int, user_id: str, status: str) -> bool:
        if status not in STATUSES:
            raise ValueError(f"invalid reminder status: {status}")
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE reminders
                SET status = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND status != 'deleted'
                """,
                (status, _now_iso(), reminder_id, user_id),
            )
            return cursor.rowcount > 0

    def due_active(self, now_iso: str, limit: int = 50) -> list[Reminder]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM reminders
                WHERE status = 'active' AND remind_at <= ?
                ORDER BY remind_at ASC, id ASC
                LIMIT ?
                """,
                (now_iso, limit),
            ).fetchall()
        return [_row_to_reminder(row) for row in rows]

    def mark_sent(self, reminder_id: int) -> None:
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE reminders
                SET status = 'sent', sent_at = ?, updated_at = ?
                WHERE id = ? AND status = 'active'
                """,
                (now, now, reminder_id),
            )

    def mark_failed(self, reminder_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE reminders
                SET status = 'failed', updated_at = ?
                WHERE id = ? AND status = 'active'
                """,
                (_now_iso(), reminder_id),
            )

    def counts(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM reminders GROUP BY status"
            ).fetchall()
        return {str(row["status"]): int(row["count"]) for row in rows}


def _row_to_reminder(row: sqlite3.Row) -> Reminder:
    return Reminder(
        id=int(row["id"]),
        user_id=str(row["user_id"]),
        chat_id=str(row["chat_id"]),
        text=str(row["text"]),
        remind_at=str(row["remind_at"]),
        timezone=str(row["timezone"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        sent_at=str(row["sent_at"]) if row["sent_at"] else None,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

from pathlib import Path

from app.reminder_store import ReminderStore


def test_reminder_crud_and_user_isolation(tmp_path: Path) -> None:
    store = ReminderStore(tmp_path / "reminders.db")
    reminder = store.create(
        user_id="user-1",
        chat_id="chat-1",
        text="Take medicine",
        remind_at="2026-06-01T01:30:00+00:00",
        timezone_name="Asia/Shanghai",
    )

    assert reminder.id > 0
    assert len(store.list_for_user("user-1")) == 1
    assert store.list_for_user("user-2") == []

    assert store.set_status_for_user(reminder.id, "user-2", "deleted") is False
    assert store.set_status_for_user(reminder.id, "user-1", "deleted") is True
    assert store.list_for_user("user-1") == []

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


class AuditLogAdapter:
    def __init__(self, log_dir: Path | str):
        self.path = Path(log_dir) / "audit.log"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        channel: str,
        user_id: int | None,
        action: str,
        project: str | None,
        success: bool,
        duration_ms: int,
        message: str,
    ) -> None:
        row = "\t".join(
            [
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                _clean(channel),
                _clean(user_id or ""),
                _clean(action),
                _clean(project or ""),
                "success" if success else "failure",
                _clean(duration_ms),
                _clean(message)[:1000],
            ]
        )
        with self.path.open("a", encoding="utf-8") as file:
            file.write(row + "\n")


def _clean(value: object) -> str:
    return str(value).replace("\r", " ").replace("\n", " ").replace("\t", " ").strip()

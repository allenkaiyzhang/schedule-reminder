from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path


logger = logging.getLogger(__name__)


def _clean(value: object) -> str:
    text = str(value)
    return text.replace("\r", " ").replace("\n", " ").replace("\t", " ").strip()


def write_audit(
    user_id: int | None,
    command: str,
    project: str | None,
    success: bool,
    duration_ms: int,
    message: str,
    *,
    log_path: Path | str = Path("./logs/audit.log"),
) -> None:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = "\t".join(
        [
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            _clean(user_id or ""),
            _clean(command),
            _clean(project or ""),
            "success" if success else "failure",
            _clean(duration_ms),
            _clean(message)[:1000],
        ]
    )
    try:
        with path.open("a", encoding="utf-8") as file:
            file.write(row + "\n")
    except OSError:
        logger.exception("Failed to write audit log")

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RemoteScriptResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int | None
    duration_ms: int
    timed_out: bool = False


def run_remote_script(
    project_config: dict[str, Any],
    script_name: str,
    args: list[str] | None = None,
) -> RemoteScriptResult:
    scripts = project_config.get("scripts") or {}
    script_path = scripts.get(script_name)
    if not script_path:
        raise KeyError(script_name)

    ssh = project_config.get("_ssh") or {}
    key_path = str(ssh["key_path"])
    timeout_seconds = int(ssh["timeout_seconds"])
    port = int(project_config.get("port", 22))
    user = str(project_config["user"])
    host = str(project_config["host"])

    command = [
        "ssh",
        "-i",
        key_path,
        "-p",
        str(port),
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={timeout_seconds}",
        f"{user}@{host}",
        str(script_path),
    ]
    if args:
        command.extend(str(item) for item in args)

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            shell=False,
            check=False,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        return RemoteScriptResult(
            success=completed.returncode == 0,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            returncode=completed.returncode,
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return RemoteScriptResult(
            success=False,
            stdout=(exc.stdout or "") if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "") if isinstance(exc.stderr, str) else "",
            returncode=None,
            duration_ms=duration_ms,
            timed_out=True,
        )
    except OSError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return RemoteScriptResult(
            success=False,
            stdout="",
            stderr=str(exc),
            returncode=None,
            duration_ms=duration_ms,
        )

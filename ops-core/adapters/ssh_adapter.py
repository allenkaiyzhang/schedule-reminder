from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SSHResult:
    success: bool
    stdout: str
    stderr: str
    returncode: int | None
    duration_ms: int
    timed_out: bool = False


class SSHAdapter:
    def __init__(self, *, key_path: str, timeout_seconds: int):
        self.key_path = key_path
        self.timeout_seconds = timeout_seconds

    def run_script(
        self,
        project_config: dict[str, Any],
        script_name: str,
        args: list[str] | None = None,
    ) -> SSHResult:
        scripts = project_config.get("scripts") or {}
        script_path = scripts.get(script_name)
        if not script_path:
            raise KeyError(script_name)

        command = [
            "ssh",
            "-i",
            self.key_path,
            "-p",
            str(int(project_config.get("port", 22))),
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={self.timeout_seconds}",
            f"{project_config['user']}@{project_config['host']}",
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
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
            return SSHResult(
                success=completed.returncode == 0,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
                returncode=completed.returncode,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except subprocess.TimeoutExpired as exc:
            return SSHResult(
                success=False,
                stdout=exc.stdout if isinstance(exc.stdout, str) else "",
                stderr=exc.stderr if isinstance(exc.stderr, str) else "",
                returncode=None,
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=True,
            )
        except OSError as exc:
            return SSHResult(
                success=False,
                stdout="",
                stderr=str(exc),
                returncode=None,
                duration_ms=int((time.monotonic() - started) * 1000),
            )

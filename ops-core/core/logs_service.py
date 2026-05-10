from __future__ import annotations

from adapters.ssh_adapter import SSHAdapter
from core.project_registry import ProjectRegistry


class LogsService:
    def __init__(self, registry: ProjectRegistry, ssh: SSHAdapter, default_lines: int):
        self.registry = registry
        self.ssh = ssh
        self.default_lines = default_lines

    def get_logs(self, project: str, lines: int | None) -> dict:
        line_count = self._sanitize_lines(lines)
        config = self.registry.get_project(project)
        if config is None:
            return _error(project, "logs", "unknown_project", f"未知项目：{project}", 0)
        if "logs" not in (config.get("scripts") or {}):
            return _error(project, "logs", "script_not_configured", f"项目 {project} 未配置 logs 脚本", 0)

        result = self.ssh.run_script(config, "logs", [str(line_count)])
        if result.timed_out:
            return _error(project, "logs", "ssh_timeout", "远程执行超时", result.duration_ms)
        if not result.success:
            return _error(
                project,
                "logs",
                "ssh_failed",
                "远程脚本执行失败\n" + ((result.stderr or "")[-1000:] or "无 stderr 输出"),
                result.duration_ms,
            )
        message = (result.stdout or "").strip() or "命令执行完成，但没有输出"
        return {
            "ok": True,
            "project": project,
            "action": "logs",
            "message": _tail(message, 3500),
            "_duration_ms": result.duration_ms,
        }

    def _sanitize_lines(self, lines: int | None) -> int:
        if lines is None:
            return min(max(1, self.default_lines), 300)
        return min(max(1, int(lines)), 300)


def _error(project: str, action: str, error: str, message: str, duration_ms: int) -> dict:
    return {
        "ok": False,
        "project": project,
        "action": action,
        "error": error,
        "message": message,
        "_duration_ms": duration_ms,
    }


def _tail(text: str, length: int) -> str:
    return text[-length:] if len(text) > length else text

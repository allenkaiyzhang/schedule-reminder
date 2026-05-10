from __future__ import annotations

from adapters.ssh_adapter import SSHAdapter
from core.project_registry import ProjectRegistry


class StatusService:
    def __init__(self, registry: ProjectRegistry, ssh: SSHAdapter):
        self.registry = registry
        self.ssh = ssh

    def get_status(self, project: str) -> dict:
        config = self.registry.get_project(project)
        if config is None:
            return _error(project, "status", "unknown_project", f"未知项目：{project}", 0)
        if "status" not in (config.get("scripts") or {}):
            return _error(project, "status", "script_not_configured", f"项目 {project} 未配置 status 脚本", 0)

        result = self.ssh.run_script(config, "status")
        if result.timed_out:
            return _error(project, "status", "ssh_timeout", "远程执行超时", result.duration_ms)
        if not result.success:
            return _error(
                project,
                "status",
                "ssh_failed",
                "远程脚本执行失败\n" + ((result.stderr or "")[-1000:] or "无 stderr 输出"),
                result.duration_ms,
            )
        message = (result.stdout or "").strip() or "命令执行完成，但没有输出"
        return {
            "ok": True,
            "project": project,
            "action": "status",
            "message": _tail(message, 3500),
            "data": {"service_active": _service_active(message)},
            "_duration_ms": result.duration_ms,
        }


def _service_active(output: str) -> str:
    for line in output.splitlines():
        value = line.strip().lower()
        if value in {"active", "inactive", "failed", "unknown"}:
            return value
        if "active:" in value and "active (running)" in value:
            return "active"
        if "active:" in value and "inactive" in value:
            return "inactive"
    return "unknown"


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

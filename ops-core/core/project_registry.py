from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ProjectRegistry:
    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)

    def list_projects(self) -> list[str]:
        return sorted(self.load_projects())

    def get_project(self, project: str) -> dict[str, Any] | None:
        return self.load_projects().get(project)

    def load_projects(self) -> dict[str, dict[str, Any]]:
        if not self.config_path.exists():
            return {}
        with self.config_path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        projects = data.get("projects") or {}
        if not isinstance(projects, dict):
            return {}
        return {
            str(name): config
            for name, config in projects.items()
            if isinstance(config, dict)
        }

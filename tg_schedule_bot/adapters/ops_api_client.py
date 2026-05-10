from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class OpsApiClient:
    base_url: str
    api_token: str
    timeout_seconds: float = 15

    def get_projects(self, *, user_id: int, chat_id: int | None = None) -> dict[str, Any]:
        return self._request("GET", "/api/projects", user_id=user_id, chat_id=chat_id)

    def get_project_status(self, project: str, *, user_id: int, chat_id: int | None = None) -> dict[str, Any]:
        return self._request("GET", f"/api/projects/{project}/status", user_id=user_id, chat_id=chat_id)

    def get_project_logs(
        self,
        project: str,
        lines: int | None,
        *,
        user_id: int,
        chat_id: int | None = None,
    ) -> dict[str, Any]:
        params = {"lines": lines} if lines is not None else None
        return self._request(
            "GET",
            f"/api/projects/{project}/logs",
            user_id=user_id,
            chat_id=chat_id,
            params=params,
        )

    def pull_notifications(self, project: str, *, user_id: int, chat_id: int | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/projects/{project}/pull-notifications",
            user_id=user_id,
            chat_id=chat_id,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        user_id: int,
        chat_id: int | None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "X-Channel": "telegram",
            "X-User-Id": str(user_id),
        }
        if chat_id is not None:
            headers["X-Chat-Id"] = str(chat_id)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.request(
                    method,
                    self.base_url + path,
                    headers=headers,
                    params=params,
                )
            try:
                data = response.json()
            except ValueError:
                return {"ok": False, "error": "bad_response", "message": response.text[-1000:]}
            if response.status_code >= 400:
                return {
                    "ok": False,
                    "error": data.get("detail") or "http_error",
                    "message": data.get("message") or str(data.get("detail") or "请求失败"),
                }
            return data
        except httpx.TimeoutException:
            return {"ok": False, "error": "ops_api_timeout", "message": "ops-core 请求超时"}
        except httpx.HTTPError as exc:
            return {"ok": False, "error": "ops_api_error", "message": str(exc)}

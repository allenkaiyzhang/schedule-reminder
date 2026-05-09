from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import httpx

from ai.prompts import day_summary_prompt, productivity_prompt, schedule_parse_prompt
from ai.schemas import (
    ParsedAISchedule,
    ProductivityAnalysis,
    validate_productivity_json,
    validate_schedule_json,
)
from config import Settings


logger = logging.getLogger("ai")


class AIProvider(ABC):
    @abstractmethod
    async def parse_schedule(
        self, text: str, *, timezone_name: str, now: datetime
    ) -> ParsedAISchedule:
        raise NotImplementedError

    @abstractmethod
    async def summarize_day(self, kind: str, schedules: list[dict[str, Any]]) -> str:
        raise NotImplementedError

    @abstractmethod
    async def analyze_productivity(
        self, rows: list[dict[str, Any]]
    ) -> ProductivityAnalysis:
        raise NotImplementedError


class DisabledAIProvider(AIProvider):
    async def parse_schedule(
        self, text: str, *, timezone_name: str, now: datetime
    ) -> ParsedAISchedule:
        raise RuntimeError("AI 未启用")

    async def summarize_day(self, kind: str, schedules: list[dict[str, Any]]) -> str:
        return "AI 总结未启用。"

    async def analyze_productivity(
        self, rows: list[dict[str, Any]]
    ) -> ProductivityAnalysis:
        return validate_productivity_json(
            {
                "completion_rate": 0,
                "productivity_score": 0,
                "most_delayed_task_type": None,
                "peak_productive_hours": [],
                "streak_days": 0,
                "suggestions": ["AI 分析未启用。"],
            }
        )


class OpenAICompatibleProvider(AIProvider):
    def __init__(
        self,
        *,
        provider_name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ):
        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def parse_schedule(
        self, text: str, *, timezone_name: str, now: datetime
    ) -> ParsedAISchedule:
        prompt = schedule_parse_prompt(text, timezone_name=timezone_name, now=now)
        response = await self._chat_json(prompt, task="parse_schedule")
        try:
            parsed = validate_schedule_json(response)
        except Exception:
            logger.exception("AI 解析结果校验失败 response=%s", response)
            raise
        logger.info("AI 解析结果校验成功 title=%s start_at=%s", parsed.title, parsed.start_at)
        return parsed

    async def summarize_day(self, kind: str, schedules: list[dict[str, Any]]) -> str:
        prompt = day_summary_prompt(kind, schedules)
        return await self._chat_text(prompt, task="summarize_day")

    async def analyze_productivity(
        self, rows: list[dict[str, Any]]
    ) -> ProductivityAnalysis:
        prompt = productivity_prompt(rows)
        response = await self._chat_json(prompt, task="analyze_productivity")
        return validate_productivity_json(response)

    async def _chat_json(self, prompt: str, *, task: str) -> str:
        return await self._chat(prompt, task=task, json_mode=True)

    async def _chat_text(self, prompt: str, *, task: str) -> str:
        return await self._chat(prompt, task=task, json_mode=False)

    async def _chat(self, prompt: str, *, task: str, json_mode: bool) -> str:
        started = time.perf_counter()
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你只能分析和生成文本，不允许控制数据库、调度器或外部系统。",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "AI 调用失败 provider=%s task=%s latency_ms=%s prompt=%s",
                self.provider_name,
                task,
                latency_ms,
                prompt,
            )
            raise

        latency_ms = int((time.perf_counter() - started) * 1000)
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        logger.info(
            "AI 调用完成 provider=%s task=%s latency_ms=%s usage=%s prompt=%s response=%s",
            self.provider_name,
            task,
            latency_ms,
            json.dumps(usage, ensure_ascii=False),
            prompt,
            content,
        )
        return content


def build_ai_provider(settings: Settings) -> AIProvider:
    provider = settings.ai_provider
    if provider in {"", "disabled", "none", "off"}:
        return DisabledAIProvider()

    defaults = {
        "openai": ("https://api.openai.com/v1", "gpt-4o-mini"),
        "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat"),
        "gemini": (
            "https://generativelanguage.googleapis.com/v1beta/openai",
            "gemini-1.5-flash",
        ),
    }
    if provider not in defaults:
        raise RuntimeError(f"不支持的 AI_PROVIDER: {provider}")
    if not settings.ai_api_key:
        raise RuntimeError("启用 AI 时必须配置 AI_API_KEY")

    default_base_url, default_model = defaults[provider]
    return OpenAICompatibleProvider(
        provider_name=provider,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url or default_base_url,
        model=settings.ai_model or default_model,
        timeout_seconds=settings.ai_timeout_seconds,
    )

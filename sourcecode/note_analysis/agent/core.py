import os
from pathlib import Path
from typing import Any

import httpx


class Agent:
    """AI Agent 编排层核心

    管理 LLM 调用（Anthropic Messages API 兼容协议）、上下文窗口、Skill 加载。
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ):
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.api_url = (api_url or os.environ.get("LLM_API_URL", "")).rstrip("/")
        self.model = model
        self.max_tokens = max_tokens
        self._messages: list[dict[str, Any]] = []
        self._client = httpx.Client(timeout=120)

    def _ensure_url(self) -> str:
        if self.api_url:
            return f"{self.api_url}/v1/messages"
        return "https://api.anthropic.com/v1/messages"

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        url = self._ensure_url()
        response = self._client.post(url, json=body, headers=headers)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result

    def add_message(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})

    def add_message_blocks(self, role: str, content: list[dict[str, Any]]) -> None:
        self._messages.append({"role": role, "content": content})

    def clear_context(self) -> None:
        self._messages.clear()

    @property
    def context_size(self) -> int:
        return len(self._messages)

    def call(self, system_prompt: str | None = None) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": self._messages,
        }
        if system_prompt:
            body["system"] = system_prompt

        data = self._post(body)
        content_blocks = data.get("content", [])
        text_parts = [
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        ]
        return "\n".join(text_parts)

    def call_with_tool(self, system_prompt: str, tools: list[dict[str, Any]]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": self._messages,
            "tools": tools,
        }
        if system_prompt:
            body["system"] = system_prompt

        return self._post(body)

    def load_skill(self, skill_path: str) -> str:
        path = Path(skill_path)
        if not path.exists():
            msg = f"Skill 文件不存在: {skill_path}"
            raise FileNotFoundError(msg)
        return path.read_text(encoding="utf-8")

    def execute_skill(self, skill_path: str, context: str) -> str:
        skill_content = self.load_skill(skill_path)
        system_prompt = (
            "你正在执行以下 Skill 工作流。请严格按照流程执行。\n\n"
            f"{skill_content}"
        )
        self.add_message("user", context)
        result = self.call(system_prompt=system_prompt)
        self._messages.pop()
        return result

    def close(self) -> None:
        self._client.close()

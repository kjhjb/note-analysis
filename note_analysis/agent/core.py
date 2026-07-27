from pathlib import Path

import httpx
from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    api_key: str | None = None
    base_url: str = "https://api.anthropic.com/v1"
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096


class Agent:
    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig()
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))

    def _get_headers(self) -> dict:
        return {
            "x-api-key": self.config.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def _build_messages(
        self,
        prompt: str,
        images: list[dict] | None = None,
    ) -> list[dict]:
        content: list[dict] = [{"type": "text", "text": prompt}]
        if images:
            for img in images:
                content.append({
                    "type": "image",
                    "source": {
                        "type": img.get("type", "base64"),
                        "media_type": img["media_type"],
                        "data": img["data"],
                    },
                })
        return [{"role": "user", "content": content}]

    def _build_request_body(
        self,
        system_prompt: str,
        messages: list[dict],
    ) -> dict:
        return {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "system": system_prompt,
            "messages": messages,
        }

    async def send_message(
        self,
        prompt: str,
        system_prompt: str = "",
        images: list[dict] | None = None,
    ) -> dict:
        messages = self._build_messages(prompt, images)
        body = self._build_request_body(system_prompt, messages)
        headers = self._get_headers()
        url = f"{self.config.base_url}/messages"
        response = await self._client.post(url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()

    def load_skill(self, skill_dir: str) -> str:
        path = Path(skill_dir) / "SKILL.md"
        if not path.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")
        return path.read_text(encoding="utf-8")

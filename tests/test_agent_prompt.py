import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from note_analysis.agent.core import Agent, LLMConfig


class TestLLMConfig:
    def test_default_values(self):
        cfg = LLMConfig()
        assert cfg.api_key is None
        assert cfg.base_url == "https://api.anthropic.com/v1"
        assert cfg.model == "claude-sonnet-4-20250514"
        assert cfg.max_tokens == 4096

    def test_custom_values(self):
        cfg = LLMConfig(
            api_key="sk-test",
            base_url="https://custom.api.com/v1",
            model="gpt-4o",
            max_tokens=2048,
        )
        assert cfg.api_key == "sk-test"
        assert cfg.model == "gpt-4o"


class TestAgentMessageFormat:
    """Anthropic Messages API 消息格式构造"""

    def test_build_messages_text_only(self):
        cfg = LLMConfig(api_key="sk-test")
        agent = Agent(cfg)
        messages = agent._build_messages("你好，请分析")
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == [{"type": "text", "text": "你好，请分析"}]

    def test_build_messages_with_image(self):
        cfg = LLMConfig(api_key="sk-test")
        agent = Agent(cfg)
        messages = agent._build_messages(
            "描述图片",
            images=[{"type": "base64", "media_type": "image/jpeg", "data": "fakebase64=="}],
        )
        assert len(messages) == 1
        content = messages[0]["content"]
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image"
        assert content[1]["source"]["media_type"] == "image/jpeg"


class TestAgentRequestConstruction:
    """完整的 API 请求体构造"""

    def test_build_request_body(self):
        cfg = LLMConfig(api_key="sk-test", model="claude-sonnet-4-20250514")
        agent = Agent(cfg)
        body = agent._build_request_body(
            system_prompt="你是分析助手",
            messages=[{"role": "user", "content": [{"type": "text", "text": "分析"}]}],
        )
        assert body["model"] == "claude-sonnet-4-20250514"
        assert body["system"] == "你是分析助手"
        assert body["max_tokens"] == 4096
        assert "stream" not in body

    def test_request_headers(self):
        cfg = LLMConfig(api_key="sk-test")
        agent = Agent(cfg)
        headers = agent._get_headers()
        assert headers["x-api-key"] == "sk-test"
        assert headers["anthropic-version"] == "2023-06-01"
        assert headers["content-type"] == "application/json"


class TestAgentApiCall:
    """mock HTTP 客户端验证 API 调用"""

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        mock_response = {
            "id": "msg_01",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "这是分析结果"}],
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }
        cfg = LLMConfig(api_key="sk-test")
        agent = Agent(cfg)

        with patch.object(agent, "_client") as mock_client:
            mock_client.post = AsyncMock()
            mock_response_obj = MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post.return_value = mock_response_obj

            result = await agent.send_message("分析这道题", system_prompt="你是数学老师")

        assert result["content"][0]["text"] == "这是分析结果"
        assert result["stop_reason"] == "end_turn"

        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["headers"]["x-api-key"] == "sk-test"
        body = call_kwargs["json"]
        assert body["system"] == "你是数学老师"

    @pytest.mark.asyncio
    async def test_send_message_failure(self):
        cfg = LLMConfig(api_key="sk-test")
        agent = Agent(cfg)

        with patch.object(agent, "_client") as mock_client:
            mock_client.post = AsyncMock()
            mock_response_obj = MagicMock(spec=httpx.Response)
            mock_response_obj.status_code = 401
            mock_response_obj.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Unauthorized", request=MagicMock(), response=mock_response_obj
            )
            mock_client.post.return_value = mock_response_obj

            with pytest.raises(httpx.HTTPStatusError):
                await agent.send_message("分析")


class TestAgentSkillLoading:
    """Skill 加载能力"""

    def test_load_skill_prompts(self, tmp_path):
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# Test Skill\n\n## Workflow\n\n1. 读取输入\n2. 生成输出\n", encoding="utf-8"
        )

        cfg = LLMConfig(api_key="sk-test")
        agent = Agent(cfg)
        skill_content = agent.load_skill(str(skill_dir))

        assert "# Test Skill" in skill_content
        assert "## Workflow" in skill_content

    def test_load_skill_not_found(self, tmp_path):
        cfg = LLMConfig(api_key="sk-test")
        agent = Agent(cfg)
        with pytest.raises(FileNotFoundError):
            agent.load_skill(str(tmp_path / "nonexistent"))

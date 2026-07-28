import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from note_analysis.agent.core import Agent


def test_agent_initialization():
    agent = Agent(api_key="test-key", api_url="https://test.api.com")
    assert agent.api_key == "test-key"
    assert agent.api_url == "https://test.api.com"
    assert agent.model == "claude-sonnet-4-20250514"
    assert agent.max_tokens == 4096


def test_agent_message_management():
    agent = Agent(api_key="test")
    assert agent.context_size == 0
    agent.add_message("user", "你好")
    assert agent.context_size == 1
    agent.add_message("assistant", "你好，有什么可以帮助的？")
    assert agent.context_size == 2
    agent.clear_context()
    assert agent.context_size == 0


def test_agent_ensure_url_default():
    agent = Agent(api_key="test")
    assert agent._ensure_url() == "https://api.anthropic.com/v1/messages"


def test_agent_ensure_url_custom():
    agent = Agent(api_key="test", api_url="https://custom.api.com")
    assert agent._ensure_url() == "https://custom.api.com/v1/messages"


def test_agent_ensure_url_trailing_slash():
    agent = Agent(api_key="test", api_url="https://custom.api.com/")
    assert agent._ensure_url() == "https://custom.api.com/v1/messages"


@patch("httpx.Client.post")
def test_agent_call(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "Hello!"}]
    }
    mock_post.return_value = mock_response

    agent = Agent(api_key="test-key", api_url="https://test.api.com")
    agent.add_message("user", "Say hello")
    result = agent.call(system_prompt="Be friendly")

    assert result == "Hello!"
    mock_post.assert_called_once()
    call_args = mock_post.call_args[1]
    assert call_args["json"]["model"] == "claude-sonnet-4-20250514"
    assert call_args["json"]["system"] == "Be friendly"
    assert len(call_args["json"]["messages"]) == 1


@patch("httpx.Client.post")
def test_agent_call_with_tool(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "tool_use", "name": "test_tool", "input": {}}]
    }
    mock_post.return_value = mock_response

    agent = Agent(api_key="test-key", api_url="https://test.api.com")
    agent.add_message("user", "Use a tool")
    tools = [{"name": "test_tool", "description": "A test tool"}]
    result = agent.call_with_tool(system_prompt="Use tools", tools=tools)

    assert "tool_use" in str(result)
    mock_post.assert_called_once()
    call_args = mock_post.call_args[1]
    assert "tools" in call_args["json"]


def test_load_skill(tmp_path: Path) -> None:
    skill_file = tmp_path / "test_skill.md"
    skill_file.write_text("# Test Skill\nDo something", encoding="utf-8")

    agent = Agent(api_key="test")
    content = agent.load_skill(str(skill_file))
    assert "# Test Skill" in content
    assert "Do something" in content


def test_load_skill_not_found() -> None:
    agent = Agent(api_key="test")
    with pytest.raises(FileNotFoundError):
        agent.load_skill("/nonexistent/skill.md")


@patch("note_analysis.agent.core.Agent.call")
def test_execute_skill(mock_call: MagicMock, tmp_path: Path) -> None:
    mock_call.return_value = "Skill executed"
    skill_file = tmp_path / "test_skill.md"
    skill_file.write_text("# Skill\nDo X", encoding="utf-8")

    agent = Agent(api_key="test")
    result = agent.execute_skill(str(skill_file), "Some context")
    assert result == "Skill executed"


@patch("note_analysis.agent.core.load_dotenv")
def test_agent_loads_dotenv(mock_load_dotenv: MagicMock) -> None:
    Agent(api_key="test", dotenv_path="/fake/.env")
    mock_load_dotenv.assert_called_once_with("/fake/.env")


@patch("note_analysis.agent.core.load_dotenv")
def test_agent_skips_dotenv_when_not_provided(mock_load_dotenv: MagicMock) -> None:
    Agent(api_key="test")
    mock_load_dotenv.assert_not_called()


@patch("note_analysis.agent.core.load_dotenv")
def test_agent_uses_api_key_from_env_after_dotenv(mock_load_dotenv: MagicMock) -> None:
    mock_load_dotenv.side_effect = lambda p: os.environ.update({"LLM_API_KEY": "env-file-key"})
    agent = Agent(dotenv_path="/fake/.env")
    assert agent.api_key == "env-file-key"
    os.environ.pop("LLM_API_KEY", None)

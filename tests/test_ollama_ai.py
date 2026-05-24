"""Tests for Ollama AI adapter — Phase 5."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from adapters.ai.base import AIProviderError, AIStructuredOutputError
from adapters.ai.ollama import OllamaAI
from core.models import ExtractionResult

VALID_EXTRACTION = {
    "person_name": "Jerry",
    "interaction_type": "casual",
    "summary": "Brief chat about music",
    "facts": [{"category": "interest", "content": "likes Fall Out Boy"}],
    "tags_added": ["music-fan"],
    "loops": [{"description": "Jerry sending album link", "due_date": "2026-05-29"}],
}


def _mock_response(data: dict | str, status_code: int = 200) -> httpx.Response:
    """Build a mock httpx Response."""
    if isinstance(data, dict):
        body = json.dumps(data)
    else:
        body = data
    return httpx.Response(
        status_code=status_code,
        content=body.encode(),
        request=httpx.Request("POST", "http://test/api/chat"),
    )


def _chat_response(content: str) -> httpx.Response:
    """Build a mock Ollama chat response."""
    return _mock_response({"message": {"content": content}})


class TestOllamaInit:
    def test_defaults(self):
        ai = OllamaAI()
        assert ai.provider_name() == "ollama"
        assert ai.model == "llama3.1:8b"
        assert ai.base_url == "http://localhost:11434"

    def test_custom_config(self):
        ai = OllamaAI(
            base_url="http://gpu-box:11434/",
            model="mistral:7b",
        )
        assert ai.base_url == "http://gpu-box:11434"
        assert ai.model == "mistral:7b"


class TestExtractStructured:
    async def test_successful_extraction(self):
        ai = OllamaAI()
        ai._client.post = AsyncMock(
            return_value=_chat_response(json.dumps(VALID_EXTRACTION))
        )

        result = await ai.extract_structured(
            system_prompt="Extract data",
            user_input="Jerry likes Fall Out Boy",
            response_model=ExtractionResult,
        )

        assert result.person_name == "Jerry"
        assert result.interaction_type.value == "casual"
        assert len(result.facts) == 1
        assert result.facts[0].content == "likes Fall Out Boy"
        assert result.tags_added == ["music-fan"]
        assert len(result.loops) == 1

    async def test_retry_on_bad_json_then_succeeds(self):
        ai = OllamaAI()
        ai._client.post = AsyncMock(
            side_effect=[
                _chat_response("not valid json {{{"),
                _chat_response(json.dumps(VALID_EXTRACTION)),
            ]
        )

        result = await ai.extract_structured("prompt", "input", ExtractionResult)
        assert result.person_name == "Jerry"
        assert ai._client.post.call_count == 2

    async def test_retry_on_invalid_schema_then_succeeds(self):
        ai = OllamaAI()
        incomplete = {"person_name": "Jerry"}
        ai._client.post = AsyncMock(
            side_effect=[
                _chat_response(json.dumps(incomplete)),
                _chat_response(json.dumps(VALID_EXTRACTION)),
            ]
        )

        result = await ai.extract_structured("prompt", "input", ExtractionResult)
        assert result.person_name == "Jerry"

    async def test_retry_exhausted_raises(self):
        ai = OllamaAI()
        ai._client.post = AsyncMock(
            side_effect=[
                _chat_response("bad json"),
                _chat_response("still bad json"),
            ]
        )

        with pytest.raises(AIStructuredOutputError, match="after retry"):
            await ai.extract_structured("prompt", "input", ExtractionResult)

    async def test_connection_error_raised(self):
        ai = OllamaAI()
        ai._client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with pytest.raises(AIProviderError, match="Cannot connect"):
            await ai.extract_structured("prompt", "input", ExtractionResult)

    async def test_timeout_error_raised(self):
        ai = OllamaAI()
        ai._client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        with pytest.raises(AIProviderError, match="timed out"):
            await ai.extract_structured("prompt", "input", ExtractionResult)

    async def test_http_error_raised(self):
        ai = OllamaAI()
        ai._client.post = AsyncMock(
            return_value=_mock_response("error", status_code=500)
        )

        with pytest.raises(AIProviderError, match="HTTP 500"):
            await ai.extract_structured("prompt", "input", ExtractionResult)


class TestGenerateText:
    async def test_successful_generation(self):
        ai = OllamaAI()
        ai._client.post = AsyncMock(
            return_value=_chat_response("Jerry is a colleague at Acme.")
        )

        result = await ai.generate_text(
            system_prompt="Generate a brief",
            user_input="Brief me on Jerry",
        )

        assert "Jerry" in result
        assert "Acme" in result

    async def test_connection_error(self):
        ai = OllamaAI()
        ai._client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with pytest.raises(AIProviderError, match="Cannot connect"):
            await ai.generate_text("prompt", "input")


class TestPromptAgnostic:
    """Both adapters accept the same prompt and produce valid results."""

    async def test_same_prompt_both_providers(self):
        from core.prompts.extraction import (
            EXTRACTION_SYSTEM_PROMPT,
            build_extraction_prompt,
        )

        user_prompt = build_extraction_prompt(
            "Water cooler with Jerry, he likes Fall Out Boy"
        )

        from adapters.ai.anthropic_api import AnthropicAI

        test_key = "test-fake-key"  # pragma: allowlist secret
        anthropic_ai = AnthropicAI(api_key=test_key)

        from unittest.mock import MagicMock as MM

        tool_block = MM()
        tool_block.type = "tool_use"
        tool_block.input = VALID_EXTRACTION
        anthropic_resp = MM()
        anthropic_resp.content = [tool_block]
        anthropic_ai._client.messages.create = AsyncMock(return_value=anthropic_resp)

        ollama_ai = OllamaAI()
        ollama_ai._client.post = AsyncMock(
            return_value=_chat_response(json.dumps(VALID_EXTRACTION))
        )

        result_a = await anthropic_ai.extract_structured(
            EXTRACTION_SYSTEM_PROMPT, user_prompt, ExtractionResult
        )
        result_o = await ollama_ai.extract_structured(
            EXTRACTION_SYSTEM_PROMPT, user_prompt, ExtractionResult
        )

        assert result_a.person_name == result_o.person_name
        assert result_a.interaction_type == result_o.interaction_type
        assert len(result_a.facts) == len(result_o.facts)

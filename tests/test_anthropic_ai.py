"""Tests for Anthropic AI adapter — Phase 5."""

from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest

from adapters.ai.anthropic_api import AnthropicAI
from adapters.ai.base import (
    AIAuthError,
    AIProviderError,
    AIRateLimitError,
    AIStructuredOutputError,
)
from core.models import ExtractionResult


def _make_tool_use_response(data: dict) -> MagicMock:
    """Build a mock Anthropic response with a tool_use block."""
    block = MagicMock()
    block.type = "tool_use"
    block.input = data
    response = MagicMock()
    response.content = [block]
    return response


def _make_text_response(text: str) -> MagicMock:
    """Build a mock Anthropic response with a text block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


VALID_EXTRACTION = {
    "person_name": "Jerry",
    "interaction_type": "casual",
    "summary": "Brief chat about music",
    "facts": [{"category": "interest", "content": "likes Fall Out Boy"}],
    "tags_added": ["music-fan"],
    "loops": [{"description": "Jerry sending album link", "due_date": "2026-05-29"}],
}


class TestAnthropicInit:
    def test_missing_key_raises(self):
        with pytest.raises(AIAuthError):
            AnthropicAI(api_key=None)

    def test_empty_key_raises(self):
        with pytest.raises(AIAuthError):
            AnthropicAI(api_key="")

    def test_valid_key_succeeds(self):
        ai = AnthropicAI(api_key="test-key")
        assert ai.provider_name() == "anthropic"
        assert ai.model == "claude-sonnet-4-5"


class TestExtractStructured:
    async def test_successful_extraction(self):
        ai = AnthropicAI(api_key="test-key")
        mock_response = _make_tool_use_response(VALID_EXTRACTION)
        ai._client.messages.create = AsyncMock(return_value=mock_response)

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

    async def test_auth_error_raised(self):
        ai = AnthropicAI(api_key="bad-key")
        ai._client.messages.create = AsyncMock(
            side_effect=anthropic.AuthenticationError(
                message="invalid key",
                response=MagicMock(status_code=401),
                body=None,
            )
        )

        with pytest.raises(AIAuthError, match="auth failed"):
            await ai.extract_structured("prompt", "input", ExtractionResult)

    async def test_rate_limit_retries_then_succeeds(self):
        ai = AnthropicAI(api_key="test-key")
        mock_response = _make_tool_use_response(VALID_EXTRACTION)
        ai._client.messages.create = AsyncMock(
            side_effect=[
                anthropic.RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429),
                    body=None,
                ),
                mock_response,
            ]
        )

        result = await ai.extract_structured("prompt", "input", ExtractionResult)
        assert result.person_name == "Jerry"
        assert ai._client.messages.create.call_count == 2

    async def test_rate_limit_retries_then_fails(self):
        ai = AnthropicAI(api_key="test-key")
        rate_err = anthropic.RateLimitError(
            message="rate limited",
            response=MagicMock(status_code=429),
            body=None,
        )
        ai._client.messages.create = AsyncMock(side_effect=[rate_err, rate_err])

        with pytest.raises(AIRateLimitError, match="after retry"):
            await ai.extract_structured("prompt", "input", ExtractionResult)

    async def test_invalid_structure_raises(self):
        ai = AnthropicAI(api_key="test-key")
        bad_data = {"person_name": "Jerry"}
        mock_response = _make_tool_use_response(bad_data)
        ai._client.messages.create = AsyncMock(return_value=mock_response)

        with pytest.raises(AIStructuredOutputError, match="invalid structure"):
            await ai.extract_structured("prompt", "input", ExtractionResult)

    async def test_no_tool_use_block_raises(self):
        ai = AnthropicAI(api_key="test-key")
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "some text"
        response = MagicMock()
        response.content = [text_block]
        ai._client.messages.create = AsyncMock(return_value=response)

        with pytest.raises(AIStructuredOutputError, match="no tool_use"):
            await ai.extract_structured("prompt", "input", ExtractionResult)

    async def test_api_error_raised(self):
        ai = AnthropicAI(api_key="test-key")
        ai._client.messages.create = AsyncMock(
            side_effect=anthropic.APIError(
                message="server error",
                request=MagicMock(),
                body=None,
            )
        )

        with pytest.raises(AIProviderError, match="API error"):
            await ai.extract_structured("prompt", "input", ExtractionResult)


class TestGenerateText:
    async def test_successful_generation(self):
        ai = AnthropicAI(api_key="test-key")
        mock_response = _make_text_response("Jerry is a colleague at Acme.")
        ai._client.messages.create = AsyncMock(return_value=mock_response)

        result = await ai.generate_text(
            system_prompt="Generate a brief",
            user_input="Brief me on Jerry",
        )

        assert "Jerry" in result
        assert "Acme" in result

    async def test_empty_response_raises(self):
        ai = AnthropicAI(api_key="test-key")
        response = MagicMock()
        response.content = []
        ai._client.messages.create = AsyncMock(return_value=response)

        with pytest.raises(AIProviderError, match="no text"):
            await ai.generate_text("prompt", "input")

    async def test_rate_limit_retries_then_succeeds(self):
        ai = AnthropicAI(api_key="test-key")
        mock_response = _make_text_response("Brief text")
        ai._client.messages.create = AsyncMock(
            side_effect=[
                anthropic.RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429),
                    body=None,
                ),
                mock_response,
            ]
        )

        result = await ai.generate_text("prompt", "input")
        assert result == "Brief text"

    async def test_auth_error_raised(self):
        ai = AnthropicAI(api_key="bad-key")
        ai._client.messages.create = AsyncMock(
            side_effect=anthropic.AuthenticationError(
                message="invalid",
                response=MagicMock(status_code=401),
                body=None,
            )
        )

        with pytest.raises(AIAuthError):
            await ai.generate_text("prompt", "input")

"""Anthropic API adapter.

Implements AIProvider using Anthropic's API. Uses tool-use for reliable
structured output.
"""

import asyncio
import logging
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from adapters.ai.base import (
    AIAuthError,
    AIProvider,
    AIProviderError,
    AIRateLimitError,
    AIStructuredOutputError,
)

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class AnthropicAI(AIProvider):
    """Anthropic implementation of AIProvider using tool-use for structured output."""

    def __init__(self, api_key: str | None, model: str = "claude-sonnet-4-5") -> None:
        if not api_key:
            raise AIAuthError("Anthropic API key is required")
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def extract_structured(
        self,
        system_prompt: str,
        user_input: str,
        response_model: type[T],
    ) -> T:
        """Extract structured output using Anthropic tool-use."""
        schema = response_model.model_json_schema()
        tool = {
            "name": "extract",
            "description": "Extract structured data from user input",
            "input_schema": schema,
        }

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_input}],
                tools=[tool],
                tool_choice={"type": "tool", "name": "extract"},
            )
        except anthropic.AuthenticationError as e:
            raise AIAuthError(f"Anthropic auth failed: {e}") from e
        except anthropic.RateLimitError:
            logger.warning("Anthropic rate limit hit, retrying after 2s")
            await asyncio.sleep(2)
            try:
                response = await self._client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_input}],
                    tools=[tool],
                    tool_choice={"type": "tool", "name": "extract"},
                )
            except anthropic.RateLimitError as e:
                raise AIRateLimitError(
                    "Anthropic rate limit exceeded after retry"
                ) from e
        except anthropic.APIError as e:
            raise AIProviderError(f"Anthropic API error: {e}") from e

        for block in response.content:
            if block.type == "tool_use":
                try:
                    return response_model.model_validate(block.input)
                except ValidationError as e:
                    raise AIStructuredOutputError(
                        f"Anthropic returned invalid structure: {e}"
                    ) from e

        raise AIStructuredOutputError("Anthropic response contained no tool_use block")

    async def generate_text(
        self,
        system_prompt: str,
        user_input: str,
        max_tokens: int = 2000,
    ) -> str:
        """Generate freeform text using the Anthropic messages API."""
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_input}],
            )
        except anthropic.AuthenticationError as e:
            raise AIAuthError(f"Anthropic auth failed: {e}") from e
        except anthropic.RateLimitError:
            logger.warning("Anthropic rate limit hit, retrying after 2s")
            await asyncio.sleep(2)
            try:
                response = await self._client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_input}],
                )
            except anthropic.RateLimitError as e:
                raise AIRateLimitError(
                    "Anthropic rate limit exceeded after retry"
                ) from e
        except anthropic.APIError as e:
            raise AIProviderError(f"Anthropic API error: {e}") from e

        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)

        if not text_parts:
            raise AIProviderError("Anthropic response contained no text")

        return "\n".join(text_parts)

    def provider_name(self) -> str:
        """Return provider identifier."""
        return "anthropic"

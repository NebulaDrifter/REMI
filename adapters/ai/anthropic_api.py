"""Anthropic API adapter.

Implements AIProvider using Anthropic's API. Uses tool-use for reliable
structured output.

Implementation: Phase 5 of BUILD_PLAN.md.
"""

# TODO (Phase 5): Implement AnthropicAI(AIProvider) here.
#
# Implementation notes:
# - Use the official `anthropic` SDK
# - For extract_structured: use tool-use to force JSON conforming to response_model
#   - Convert response_model to a JSON schema via Pydantic's model_json_schema()
#   - Define a single tool with that schema
#   - tool_choice = forced
#   - Parse the tool_use block, validate against response_model
# - For generate_text: standard messages API
# - Handle anthropic.AuthenticationError → AIAuthError
# - Handle anthropic.RateLimitError → AIRateLimitError (one retry with backoff)
# - Handle anthropic.BadRequestError appropriately
# - Configurable model via ANTHROPIC_MODEL env var
# - DO NOT use Anthropic-specific prompt formatting in the prompt itself;
#   only in the API call structure

from typing import TypeVar

from pydantic import BaseModel

from adapters.ai.base import AIProvider

T = TypeVar("T", bound=BaseModel)


class AnthropicAI(AIProvider):
    """Anthropic implementation of AIProvider.

    TODO: Implement in Phase 5.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5") -> None:
        self.api_key = api_key
        self.model = model
        # TODO: Initialize anthropic.AsyncAnthropic client

    async def extract_structured(
        self,
        system_prompt: str,
        user_input: str,
        response_model: type[T],
    ) -> T:
        raise NotImplementedError("Phase 5: implement Anthropic tool-use extraction")

    async def generate_text(
        self,
        system_prompt: str,
        user_input: str,
        max_tokens: int = 2000,
    ) -> str:
        raise NotImplementedError("Phase 5: implement Anthropic text generation")

    def provider_name(self) -> str:
        return "anthropic"

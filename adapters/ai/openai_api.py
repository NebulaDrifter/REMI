"""OpenAI API adapter.

Stub. Not implemented in v1.0. Listed as a known extension point so contributors
can add it without core changes.

When implemented, use OpenAI's structured outputs feature (response_format with
strict JSON schema) for extract_structured.
"""

from typing import TypeVar

from pydantic import BaseModel

from adapters.ai.base import AIProvider

T = TypeVar("T", bound=BaseModel)


class OpenAIAI(AIProvider):
    """OpenAI implementation of AIProvider.

    Stub — not implemented in v1.0.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        raise NotImplementedError(
            "OpenAI adapter not implemented in v1.0. "
            "Use AI_PROVIDER=anthropic or AI_PROVIDER=ollama instead."
        )

    async def extract_structured(
        self,
        system_prompt: str,
        user_input: str,
        response_model: type[T],
    ) -> T:
        raise NotImplementedError("OpenAI adapter not implemented")

    async def generate_text(
        self,
        system_prompt: str,
        user_input: str,
        max_tokens: int = 2000,
    ) -> str:
        raise NotImplementedError("OpenAI adapter not implemented")

    def provider_name(self) -> str:
        return "openai"

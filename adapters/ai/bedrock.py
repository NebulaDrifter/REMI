"""AWS Bedrock AI adapter.

Stub. Not implemented in v1.0. Use case: cloud deployments where users want to
keep AI inference inside their AWS account (no data leaving the perimeter).

When implemented, use the Converse API for cleaner multi-model support.
"""

from typing import TypeVar

from pydantic import BaseModel

from adapters.ai.base import AIProvider

T = TypeVar("T", bound=BaseModel)


class BedrockAI(AIProvider):
    """AWS Bedrock implementation of AIProvider.

    Stub — not implemented in v1.0.
    """

    def __init__(self, region: str, model: str) -> None:
        raise NotImplementedError(
            "Bedrock adapter not implemented in v1.0. "
            "Use AI_PROVIDER=anthropic or AI_PROVIDER=ollama instead."
        )

    async def extract_structured(
        self,
        system_prompt: str,
        user_input: str,
        response_model: type[T],
    ) -> T:
        raise NotImplementedError("Bedrock adapter not implemented")

    async def generate_text(
        self,
        system_prompt: str,
        user_input: str,
        max_tokens: int = 2000,
    ) -> str:
        raise NotImplementedError("Bedrock adapter not implemented")

    def provider_name(self) -> str:
        return "bedrock"

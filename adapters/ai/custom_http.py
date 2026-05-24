"""Custom HTTP AI adapter.

Stub. Not implemented in v1.0. Designed for enterprise/work scenarios where
the user must use a corporate-approved AI endpoint.

Assumes the endpoint speaks OpenAI-compatible API (the de facto standard most
corporate gateways use). One adapter, broad enterprise compatibility.

When implemented:
- POST to {endpoint}/chat/completions with OpenAI-compatible body
- Support arbitrary auth header (Bearer token, API key in header, etc.)
- Tolerate minor schema variations between corporate gateways
"""

from typing import TypeVar

from pydantic import BaseModel

from adapters.ai.base import AIProvider

T = TypeVar("T", bound=BaseModel)


class CustomHTTPAI(AIProvider):
    """OpenAI-compatible HTTP endpoint adapter.

    Stub — not implemented in v1.0.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str | None,
        model: str,
        auth_header_name: str = "Authorization",
        auth_header_format: str = "Bearer {key}",
    ) -> None:
        raise NotImplementedError(
            "Custom HTTP adapter not implemented in v1.0. "
            "Use AI_PROVIDER=anthropic or AI_PROVIDER=ollama instead."
        )

    async def extract_structured(
        self,
        system_prompt: str,
        user_input: str,
        response_model: type[T],
    ) -> T:
        raise NotImplementedError("Custom HTTP adapter not implemented")

    async def generate_text(
        self,
        system_prompt: str,
        user_input: str,
        max_tokens: int = 2000,
    ) -> str:
        raise NotImplementedError("Custom HTTP adapter not implemented")

    def provider_name(self) -> str:
        return "custom_http"

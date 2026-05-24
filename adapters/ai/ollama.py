"""Ollama AI adapter.

Implements AIProvider using a local Ollama server. No SDK — pure HTTP via httpx.

This is the second v1.0 AI adapter. Its maximal difference from Anthropic
(no auth, JSON mode parsing, local hosting) is what forces the AIProvider
interface to be honest. If both work cleanly, OpenAI/Bedrock/custom are trivial.

Implementation: Phase 5 of BUILD_PLAN.md.
"""

# TODO (Phase 5): Implement OllamaAI(AIProvider) here.
#
# Implementation notes:
# - Use httpx.AsyncClient for HTTP calls (no Ollama SDK needed)
# - For extract_structured:
#   - Use Ollama's JSON mode (format: "json" in request)
#   - Pass the Pydantic schema in the system prompt as JSON schema text
#   - Parse response, validate against response_model
#   - On JSON parse failure or schema mismatch, retry ONCE with a corrective
#     follow-up. Then give up and raise AIStructuredOutputError.
# - For generate_text: standard /api/generate endpoint
# - No auth needed (Ollama is typically local)
# - Configurable base URL and model via OLLAMA_BASE_URL and OLLAMA_MODEL
# - Handle connection errors (Ollama not running) with a clear error message
# - Smaller local models may struggle with structured output — log when retry
#   happens so users can diagnose

from typing import TypeVar

from pydantic import BaseModel

from adapters.ai.base import AIProvider

T = TypeVar("T", bound=BaseModel)


class OllamaAI(AIProvider):
    """Ollama implementation of AIProvider.

    TODO: Implement in Phase 5.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        # TODO: Initialize httpx.AsyncClient

    async def extract_structured(
        self,
        system_prompt: str,
        user_input: str,
        response_model: type[T],
    ) -> T:
        raise NotImplementedError("Phase 5: implement Ollama JSON-mode extraction")

    async def generate_text(
        self,
        system_prompt: str,
        user_input: str,
        max_tokens: int = 2000,
    ) -> str:
        raise NotImplementedError("Phase 5: implement Ollama text generation")

    def provider_name(self) -> str:
        return "ollama"

"""Abstract AI provider interface.

All AI adapters (Anthropic, Ollama, OpenAI, Bedrock, custom HTTP) implement this.
The core never imports a specific provider SDK.

Design principles:
- Two methods only: extract_structured (for structured JSON) and generate_text
  (for freeform output like briefs).
- Prompts are provider-agnostic strings. Adapter handles provider-specific
  formatting (Anthropic tool use, OpenAI structured outputs, Ollama JSON mode).
- Adapter handles retries, JSON parsing, and validation against the response
  Pydantic model.
"""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


# ============================================================================
# Exceptions
# ============================================================================


class AIProviderError(Exception):
    """Base exception for AI provider errors."""


class AIAuthError(AIProviderError):
    """Authentication or authorization failed."""


class AIRateLimitError(AIProviderError):
    """Provider rate limit hit. Adapters should retry with backoff once."""


class AIStructuredOutputError(AIProviderError):
    """Provider returned content that doesn't conform to the requested schema.

    After retries, the adapter gives up and raises this. The caller decides
    how to handle (typically: ask user to rephrase input).
    """


# ============================================================================
# Interface
# ============================================================================


class AIProvider(ABC):
    """Abstract interface for AI text generation.

    Implementations must support both structured (JSON via response_model) and
    unstructured (text) generation.
    """

    @abstractmethod
    async def extract_structured(
        self,
        system_prompt: str,
        user_input: str,
        response_model: type[T],
    ) -> T:
        """Generate structured output conforming to a Pydantic model.

        Used for the extraction prompt: raw input → ExtractionResult.

        Args:
            system_prompt: Provider-agnostic system prompt
            user_input: The user-facing prompt (already with any delimiters)
            response_model: Pydantic class the output must conform to

        Returns:
            Validated instance of response_model

        Raises:
            AIAuthError: Bad API key or auth
            AIRateLimitError: Rate limit exceeded
            AIStructuredOutputError: Couldn't get valid structured output after retries
            AIProviderError: Other provider errors
        """
        ...

    @abstractmethod
    async def generate_text(
        self,
        system_prompt: str,
        user_input: str,
        max_tokens: int = 2000,
    ) -> str:
        """Generate freeform text.

        Used for the retrieval prompt: person history → narrative brief.

        Args:
            system_prompt: Provider-agnostic system prompt
            user_input: The user-facing prompt
            max_tokens: Cap on response length

        Returns:
            Generated text string

        Raises:
            AIAuthError: Bad API key or auth
            AIRateLimitError: Rate limit exceeded
            AIProviderError: Other provider errors
        """
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Return a short identifier for logging/audit (e.g., 'anthropic', 'ollama')."""
        ...

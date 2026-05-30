"""Ollama AI adapter.

Implements AIProvider using a local Ollama server. No SDK — pure HTTP via httpx.
"""

import json
import logging
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from adapters.ai.base import (
    AIProvider,
    AIProviderError,
    AIStructuredOutputError,
)

T = TypeVar("T", bound=BaseModel)
logger = logging.getLogger(__name__)


class OllamaAI(AIProvider):
    """Ollama implementation of AIProvider using JSON mode for structured output."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3.1:8b",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=120.0,
        )

    async def _chat(
        self,
        system_prompt: str,
        user_input: str,
        json_mode: bool = False,
    ) -> str:
        """Send a chat request to Ollama and return the response text."""
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            "stream": False,
        }

        if json_mode:
            payload["format"] = "json"

        try:
            resp = await self._client.post("/api/chat", json=payload)
        except httpx.ConnectError as e:
            raise AIProviderError(
                f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?"
            ) from e
        except httpx.TimeoutException as e:
            raise AIProviderError(
                "Ollama request timed out. The model may be loading "
                "or the input may be too long."
            ) from e

        if resp.status_code != 200:
            raise AIProviderError(
                f"Ollama returned HTTP {resp.status_code}: {resp.text}"
            )

        data = resp.json()
        return data["message"]["content"]

    async def extract_structured(
        self,
        system_prompt: str,
        user_input: str,
        response_model: type[T],
    ) -> T:
        """Extract structured output using Ollama JSON mode."""
        schema = response_model.model_json_schema()
        schema_instruction = (
            "\n\nYou MUST respond with a JSON object that conforms "
            "to this schema:\n"
            f"```json\n{json.dumps(schema, indent=2)}\n```\n"
            "Respond with ONLY the JSON object, no other text."
        )

        augmented_prompt = system_prompt + schema_instruction
        raw = await self._chat(augmented_prompt, user_input, json_mode=True)

        error_msg = ""
        try:
            parsed = json.loads(raw)
            return response_model.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as first_err:
            error_msg = str(first_err)
            logger.warning(
                "Ollama structured output failed on first attempt: %s. "
                "Retrying with correction.",
                error_msg,
            )

        correction = (
            f"Your previous response was invalid: {error_msg}\n\n"
            "Please try again. Return ONLY a valid JSON object "
            "matching the schema provided."
        )
        raw_retry = await self._chat(augmented_prompt, correction, json_mode=True)

        try:
            parsed = json.loads(raw_retry)
            return response_model.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError) as e:
            raise AIStructuredOutputError(
                f"Ollama failed to produce valid structured output after retry: {e}"
            ) from e

    async def generate_text(
        self,
        system_prompt: str,
        user_input: str,
        max_tokens: int = 2000,
    ) -> str:
        """Generate freeform text using Ollama chat API."""
        return await self._chat(system_prompt, user_input, json_mode=False)

    def provider_name(self) -> str:
        """Return provider identifier."""
        return "ollama"

    async def aclose(self) -> None:
        """Close the underlying HTTP client. Used when hot-swapping models."""
        await self._client.aclose()

"""Ollama model management.

Talks to a local Ollama server to list, pull, and delete models. This is
Ollama-specific functionality that is NOT part of the provider-agnostic
``AIProvider`` interface — model lifecycle has no equivalent for hosted
providers like Anthropic or OpenAI, so it lives in its own adapter.

Pure HTTP via httpx, no SDK.
"""

import json
import logging
from collections.abc import AsyncIterator

import httpx
from pydantic import BaseModel

from adapters.ai.base import AIProviderError

logger = logging.getLogger(__name__)


class OllamaModel(BaseModel):
    """A model installed on the Ollama server."""

    name: str
    size_bytes: int = 0
    modified_at: str | None = None


class PullProgress(BaseModel):
    """One progress update from a streaming model pull."""

    status: str
    completed: int = 0
    total: int = 0
    done: bool = False
    error: str | None = None

    @property
    def percent(self) -> int:
        """Download progress as a whole-number percent (0 when unknown)."""
        if self.total <= 0:
            return 0
        return min(100, int(self.completed / self.total * 100))


class OllamaManager:
    """Manage models on a local Ollama server.

    Separate from ``OllamaAI`` (which does inference) because model management
    is an operational concern with a different lifecycle.
    """

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def list_models(self) -> list[OllamaModel]:
        """List models installed on the Ollama server."""
        try:
            resp = await self._client.get("/api/tags")
        except httpx.ConnectError as e:
            raise AIProviderError(
                f"Cannot connect to Ollama at {self.base_url}. Is it running?"
            ) from e

        if resp.status_code != 200:
            raise AIProviderError(
                f"Ollama returned HTTP {resp.status_code}: {resp.text}"
            )

        models: list[OllamaModel] = []
        for entry in resp.json().get("models", []):
            models.append(
                OllamaModel(
                    name=entry["name"],
                    size_bytes=entry.get("size", 0),
                    modified_at=entry.get("modified_at"),
                )
            )
        models.sort(key=lambda m: m.name)
        return models

    async def delete_model(self, name: str) -> None:
        """Delete a model from the Ollama server."""
        try:
            resp = await self._client.request(
                "DELETE", "/api/delete", json={"model": name}
            )
        except httpx.ConnectError as e:
            raise AIProviderError(
                f"Cannot connect to Ollama at {self.base_url}. Is it running?"
            ) from e

        if resp.status_code == 404:
            raise AIProviderError(f"Model '{name}' is not installed.")
        if resp.status_code != 200:
            raise AIProviderError(
                f"Ollama returned HTTP {resp.status_code}: {resp.text}"
            )

    async def pull_model(self, name: str) -> AsyncIterator[PullProgress]:
        """Pull a model, yielding progress updates as they stream in.

        ``name`` may be an Ollama registry name (``llama3.1:8b``) or a Hugging
        Face GGUF reference (``hf.co/user/repo:quant``). Ollama resolves both.

        Yields:
            PullProgress for each NDJSON line the server emits. The final
            update has ``done=True``; an update with ``error`` set means the
            pull failed.
        """
        payload = {"model": name, "stream": True}
        try:
            async with self._client.stream(
                "POST", "/api/pull", json=payload, timeout=None
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="replace")
                    yield PullProgress(
                        status="error",
                        error=f"Ollama returned HTTP {resp.status_code}: {body}",
                        done=True,
                    )
                    return

                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    yield self._parse_pull_line(line)
        except httpx.ConnectError as e:
            raise AIProviderError(
                f"Cannot connect to Ollama at {self.base_url}. Is it running?"
            ) from e

    @staticmethod
    def _parse_pull_line(line: str) -> PullProgress:
        """Parse one NDJSON line from /api/pull into a PullProgress."""
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return PullProgress(status="error", error=line, done=True)

        if "error" in data:
            return PullProgress(status="error", error=data["error"], done=True)

        status = data.get("status", "")
        return PullProgress(
            status=status,
            completed=data.get("completed", 0),
            total=data.get("total", 0),
            done=status == "success",
        )


# Reasonable starter models for the UI to suggest. Provider-agnostic prompts
# mean any instruct-tuned model works; these are small enough for CPU-only use.
SUGGESTED_MODELS: list[str] = [
    "llama3.2:3b",
    "llama3.1:8b",
    "qwen2.5:7b",
    "phi3.5",
]

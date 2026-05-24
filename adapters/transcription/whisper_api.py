"""OpenAI Whisper API transcription adapter.

Implements TranscriptionProvider using OpenAI's Whisper API.
"""

import asyncio
import logging
from pathlib import Path

import openai

from adapters.transcription.base import (
    AudioTooLargeError,
    TranscriptionAuthError,
    TranscriptionError,
    TranscriptionProvider,
    UnsupportedFormatError,
)

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB per Whisper API limit


class WhisperAPI(TranscriptionProvider):
    """OpenAI Whisper API implementation of TranscriptionProvider."""

    def __init__(self, api_key: str | None, model: str = "whisper-1") -> None:
        if not api_key:
            raise TranscriptionAuthError("Whisper API key is required")
        self.model = model
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> str:
        """Transcribe an audio file using the Whisper API."""
        if not audio_path.exists():
            raise TranscriptionError(f"Audio file not found: {audio_path}")

        suffix = audio_path.suffix.lower()
        if suffix not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(
                f"Format '{suffix}' not supported. "
                f"Supported: {', '.join(sorted(SUPPORTED_FORMATS))}"
            )

        file_size = audio_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise AudioTooLargeError(
                f"File size {file_size} bytes exceeds "
                f"Whisper limit of {MAX_FILE_SIZE_BYTES} bytes (25MB)"
            )

        try:
            with open(audio_path, "rb") as audio_file:
                kwargs: dict = {
                    "model": self.model,
                    "file": audio_file,
                }
                if language:
                    kwargs["language"] = language

                transcript = await self._client.audio.transcriptions.create(**kwargs)
        except openai.AuthenticationError as e:
            raise TranscriptionAuthError(f"Whisper API auth failed: {e}") from e
        except openai.RateLimitError:
            logger.warning("Whisper rate limit hit, retrying after 2s")
            await asyncio.sleep(2)
            try:
                with open(audio_path, "rb") as audio_file:
                    kwargs = {"model": self.model, "file": audio_file}
                    if language:
                        kwargs["language"] = language
                    transcript = await self._client.audio.transcriptions.create(
                        **kwargs
                    )
            except openai.RateLimitError as e:
                raise TranscriptionError(
                    "Whisper rate limit exceeded after retry"
                ) from e
        except openai.APIError as e:
            raise TranscriptionError(f"Whisper API error: {e}") from e

        return transcript.text

    def provider_name(self) -> str:
        """Return provider identifier."""
        return "whisper_api"

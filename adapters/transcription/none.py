"""Disabled transcription adapter.

Returns a clear error when audio is submitted without a transcription provider.
"""

from pathlib import Path

from adapters.transcription.base import TranscriptionError, TranscriptionProvider


class NoneTranscription(TranscriptionProvider):
    """No-op transcription provider that rejects all requests."""

    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> str:
        raise TranscriptionError(
            "Audio transcription is disabled. "
            "Set TRANSCRIPTION_PROVIDER=whisper_api and provide "
            "WHISPER_API_KEY in .env to enable audio capture."
        )

    def provider_name(self) -> str:
        return "none"

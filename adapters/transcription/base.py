"""Abstract transcription interface.

All transcription backends (Whisper API, local Whisper.cpp, AWS Transcribe)
implement this interface.
"""

from abc import ABC, abstractmethod
from pathlib import Path


# ============================================================================
# Exceptions
# ============================================================================


class TranscriptionError(Exception):
    """Base exception for transcription errors."""


class TranscriptionAuthError(TranscriptionError):
    """Authentication failed."""


class AudioTooLargeError(TranscriptionError):
    """Audio file exceeds provider's size limit."""


class UnsupportedFormatError(TranscriptionError):
    """Audio format not supported by this provider."""


# ============================================================================
# Interface
# ============================================================================


class TranscriptionProvider(ABC):
    """Abstract interface for audio-to-text transcription."""

    @abstractmethod
    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> str:
        """Transcribe an audio file to text.

        Args:
            audio_path: Local path to the audio file
            language: Optional ISO 639-1 code (e.g., "en") to hint language

        Returns:
            Plain text transcript

        Raises:
            TranscriptionAuthError: Bad API key
            AudioTooLargeError: File too big
            UnsupportedFormatError: Bad audio format
            TranscriptionError: Other failures
        """
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Short identifier for logging (e.g., 'whisper_api')."""
        ...

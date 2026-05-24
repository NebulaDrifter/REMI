"""OpenAI Whisper API transcription adapter.

Implements TranscriptionProvider using OpenAI's Whisper API.

Implementation: Phase 6 of BUILD_PLAN.md.
"""

# TODO (Phase 6): Implement WhisperAPITranscription(TranscriptionProvider).
#
# Implementation notes:
# - Use the official `openai` SDK (AsyncOpenAI client)
# - Upload audio via audio.transcriptions.create
# - Default model: whisper-1
# - Whisper's hard limit is 25MB; reject larger files with AudioTooLargeError
# - Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm
# - Map openai.AuthenticationError → TranscriptionAuthError
# - Handle transient errors with one retry

from pathlib import Path

from adapters.transcription.base import TranscriptionProvider


class WhisperAPITranscription(TranscriptionProvider):
    """OpenAI Whisper API implementation.

    TODO: Implement in Phase 6.
    """

    MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25MB per Whisper API limit

    def __init__(self, api_key: str, model: str = "whisper-1") -> None:
        self.api_key = api_key
        self.model = model
        # TODO: Initialize AsyncOpenAI client

    async def transcribe(
        self,
        audio_path: Path,
        language: str | None = None,
    ) -> str:
        raise NotImplementedError("Phase 6: implement Whisper API transcription")

    def provider_name(self) -> str:
        return "whisper_api"

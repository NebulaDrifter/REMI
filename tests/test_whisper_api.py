"""Tests for Whisper API transcription adapter — Phase 6."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import openai
import pytest

from adapters.transcription.base import (
    AudioTooLargeError,
    TranscriptionAuthError,
    TranscriptionError,
    UnsupportedFormatError,
)
from adapters.transcription.whisper_api import WhisperAPI


@pytest.fixture
def whisper():
    """Provide a WhisperAPI instance with mocked client."""
    w = WhisperAPI(
        api_key="test-fake-key",  # pragma: allowlist secret
    )
    return w


def _make_audio_file(tmp_path: Path, name: str = "test.webm", size: int = 100) -> Path:
    """Create a fake audio file."""
    path = tmp_path / name
    path.write_bytes(b"x" * size)
    return path


class TestWhisperInit:
    def test_missing_key_raises(self):
        with pytest.raises(TranscriptionAuthError):
            WhisperAPI(api_key=None)

    def test_empty_key_raises(self):
        with pytest.raises(TranscriptionAuthError):
            WhisperAPI(api_key="")

    def test_valid_key(self):
        w = WhisperAPI(
            api_key="test-key",  # pragma: allowlist secret
        )
        assert w.provider_name() == "whisper_api"
        assert w.model == "whisper-1"


class TestTranscribe:
    async def test_successful_transcription(self, whisper, tmp_path):
        audio = _make_audio_file(tmp_path)
        mock_result = MagicMock()
        mock_result.text = "Jerry likes Fall Out Boy"
        whisper._client.audio.transcriptions.create = AsyncMock(
            return_value=mock_result
        )

        result = await whisper.transcribe(audio)
        assert result == "Jerry likes Fall Out Boy"

    async def test_with_language_hint(self, whisper, tmp_path):
        audio = _make_audio_file(tmp_path)
        mock_result = MagicMock()
        mock_result.text = "transcript"
        whisper._client.audio.transcriptions.create = AsyncMock(
            return_value=mock_result
        )

        await whisper.transcribe(audio, language="en")
        call_kwargs = whisper._client.audio.transcriptions.create.call_args
        assert call_kwargs.kwargs.get("language") == "en"

    async def test_file_not_found_raises(self, whisper, tmp_path):
        missing = tmp_path / "nonexistent.webm"
        with pytest.raises(TranscriptionError, match="not found"):
            await whisper.transcribe(missing)

    async def test_unsupported_format_raises(self, whisper, tmp_path):
        audio = _make_audio_file(tmp_path, name="test.txt")
        with pytest.raises(UnsupportedFormatError, match="not supported"):
            await whisper.transcribe(audio)

    async def test_too_large_raises(self, whisper, tmp_path):
        audio = _make_audio_file(tmp_path, size=26 * 1024 * 1024)
        with pytest.raises(AudioTooLargeError, match="25MB"):
            await whisper.transcribe(audio)

    async def test_auth_error_raised(self, whisper, tmp_path):
        audio = _make_audio_file(tmp_path)
        whisper._client.audio.transcriptions.create = AsyncMock(
            side_effect=openai.AuthenticationError(
                message="invalid key",
                response=MagicMock(status_code=401),
                body=None,
            )
        )

        with pytest.raises(TranscriptionAuthError, match="auth failed"):
            await whisper.transcribe(audio)

    async def test_api_error_raised(self, whisper, tmp_path):
        audio = _make_audio_file(tmp_path)
        whisper._client.audio.transcriptions.create = AsyncMock(
            side_effect=openai.APIError(
                message="server error",
                request=MagicMock(),
                body=None,
            )
        )

        with pytest.raises(TranscriptionError, match="API error"):
            await whisper.transcribe(audio)

    async def test_rate_limit_retries_then_succeeds(self, whisper, tmp_path):
        audio = _make_audio_file(tmp_path)
        mock_result = MagicMock()
        mock_result.text = "transcript"
        whisper._client.audio.transcriptions.create = AsyncMock(
            side_effect=[
                openai.RateLimitError(
                    message="rate limited",
                    response=MagicMock(status_code=429),
                    body=None,
                ),
                mock_result,
            ]
        )

        result = await whisper.transcribe(audio)
        assert result == "transcript"


class TestSupportedFormats:
    @pytest.mark.parametrize(
        "ext",
        [".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"],
    )
    async def test_all_formats_accepted(self, whisper, tmp_path, ext):
        audio = _make_audio_file(tmp_path, name=f"test{ext}")
        mock_result = MagicMock()
        mock_result.text = "transcript"
        whisper._client.audio.transcriptions.create = AsyncMock(
            return_value=mock_result
        )

        result = await whisper.transcribe(audio)
        assert result == "transcript"

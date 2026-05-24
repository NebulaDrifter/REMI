"""Tests for config/settings.py — Phase 2."""

import pytest
from pydantic import ValidationError

from config.settings import (
    AIProviderType,
    BlobBackend,
    Settings,
    StorageBackend,
    build_ai,
    build_blob,
    build_storage,
    build_transcription,
)


class TestSettingsDefaults:
    """Settings loads with sensible defaults for local deployment."""

    def test_defaults_load_with_required_keys(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("WHISPER_API_KEY", "test-whisper-key")
        s = Settings()

        assert s.remi_deployment == "local"
        assert s.remi_host == "127.0.0.1"
        assert s.remi_port == 8000
        assert s.storage_backend == StorageBackend.SQLITE
        assert s.ai_provider == AIProviderType.ANTHROPIC
        assert s.blob_backend == BlobBackend.FILESYSTEM
        assert s.audit_log_enabled is True

    def test_cors_origins_parsing(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

        monkeypatch.setenv(
            "REMI_CORS_ORIGINS", "http://localhost:8000, http://127.0.0.1:8000"
        )
        s = Settings()
        origins = s.get_cors_origins()
        assert origins == ["http://localhost:8000", "http://127.0.0.1:8000"]


class TestSettingsValidation:
    """Bad env vars produce clear validation errors."""

    def test_missing_anthropic_key_fails(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "anthropic")

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(ValidationError, match="ANTHROPIC_API_KEY"):
            Settings()

    def test_missing_whisper_key_fails(self, monkeypatch):
        monkeypatch.setenv("TRANSCRIPTION_PROVIDER", "whisper_api")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
        monkeypatch.delenv("WHISPER_API_KEY", raising=False)
        with pytest.raises(ValidationError, match="WHISPER_API_KEY"):
            Settings()

    def test_invalid_log_level_fails(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

        monkeypatch.setenv("REMI_LOG_LEVEL", "VERBOSE")
        with pytest.raises(ValidationError, match="Log level"):
            Settings()

    def test_invalid_storage_backend_fails(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

        monkeypatch.setenv("STORAGE_BACKEND", "postgres")
        with pytest.raises(ValidationError):
            Settings()

    def test_invalid_ai_provider_fails(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

        monkeypatch.setenv("AI_PROVIDER", "gemini")
        with pytest.raises(ValidationError):
            Settings()

    def test_ollama_doesnt_require_api_key(self, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "ollama")

        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        s = Settings()
        assert s.ai_provider == AIProviderType.OLLAMA


class TestBindWarning:
    """Binding to 0.0.0.0 warns per SECURITY.md."""

    def test_bind_all_warns(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

        monkeypatch.setenv("REMI_HOST", "0.0.0.0")
        with pytest.warns(UserWarning, match="0.0.0.0"):
            Settings()


class TestFactoryStubs:
    """v1.1 stubs raise NotImplementedError with helpful messages."""

    def _settings(self, monkeypatch, **overrides):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

        for k, v in overrides.items():
            monkeypatch.setenv(k.upper(), v)
        return Settings()

    def test_dynamodb_raises(self, monkeypatch):
        s = self._settings(monkeypatch, storage_backend="dynamodb")
        with pytest.raises(NotImplementedError, match="dynamodb"):
            build_storage(s)

    def test_s3_raises(self, monkeypatch):
        s = self._settings(monkeypatch, blob_backend="s3")
        with pytest.raises(NotImplementedError, match="s3"):
            build_blob(s)

    def test_openai_ai_raises(self, monkeypatch):
        s = self._settings(monkeypatch, ai_provider="openai")
        with pytest.raises(NotImplementedError, match="openai"):
            build_ai(s)

    def test_bedrock_ai_raises(self, monkeypatch):
        s = self._settings(monkeypatch, ai_provider="bedrock")
        with pytest.raises(NotImplementedError, match="bedrock"):
            build_ai(s)

    def test_custom_ai_raises(self, monkeypatch):
        s = self._settings(monkeypatch, ai_provider="custom")
        with pytest.raises(NotImplementedError, match="custom"):
            build_ai(s)

    def test_whisper_local_raises(self, monkeypatch):
        s = self._settings(monkeypatch, transcription_provider="whisper_local")
        with pytest.raises(NotImplementedError, match="whisper_local"):
            build_transcription(s)


class TestFactorySQLite:
    """SQLite factory returns an adapter instance."""

    def test_build_sqlite_storage(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "k")

        monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
        s = Settings()
        storage = build_storage(s)
        from adapters.storage.sqlite import SQLiteStorage

        assert isinstance(storage, SQLiteStorage)

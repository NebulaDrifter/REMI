"""Settings and adapter factory.

The ONLY module that reads environment variables. Every other module receives
its config via dependency injection from here.
"""

from enum import StrEnum

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from adapters.ai.base import AIProvider
from adapters.blob.base import BlobProvider
from adapters.storage.base import StorageProvider
from adapters.transcription.base import TranscriptionProvider

# ============================================================================
# Backend enums
# ============================================================================


class StorageBackend(StrEnum):
    """Supported storage backends."""

    SQLITE = "sqlite"
    DYNAMODB = "dynamodb"


class BlobBackend(StrEnum):
    """Supported blob storage backends."""

    FILESYSTEM = "filesystem"
    S3 = "s3"


class AIProviderType(StrEnum):
    """Supported AI providers."""

    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    OPENAI = "openai"
    BEDROCK = "bedrock"
    CUSTOM = "custom"


class TranscriptionProviderType(StrEnum):
    """Supported transcription providers."""

    WHISPER_API = "whisper_api"
    WHISPER_LOCAL = "whisper_local"
    NONE = "none"


# ============================================================================
# Settings
# ============================================================================


class Settings(BaseSettings):
    """Application configuration loaded from environment variables.

    Reads from .env file automatically. Every config value has a sensible
    default for local Docker deployment.
    """

    # --- Deployment ---
    remi_deployment: str = "local"
    remi_host: str = "127.0.0.1"
    remi_port: int = 8000
    remi_log_level: str = "INFO"

    # --- Storage ---
    storage_backend: StorageBackend = StorageBackend.SQLITE
    sqlite_path: str = "./data/remi.db"

    # DynamoDB (v1.1)
    dynamodb_region: str | None = None
    dynamodb_people_table: str = "remi-people"
    dynamodb_interactions_table: str = "remi-interactions"
    dynamodb_open_loops_table: str = "remi-open-loops"
    dynamodb_audit_table: str = "remi-audit-log"

    # --- Blob storage ---
    blob_backend: BlobBackend = BlobBackend.FILESYSTEM
    blob_filesystem_path: str = "./audio_storage"
    blob_s3_bucket: str | None = None
    blob_s3_region: str | None = None
    audio_retention_days: int = 7

    # --- AI provider ---
    ai_provider: AIProviderType = AIProviderType.ANTHROPIC

    # Anthropic
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"

    # OpenAI (v1.0 stub)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    # Bedrock (v1.0 stub)
    bedrock_region: str | None = None
    bedrock_model: str | None = None

    # Custom HTTP (v1.0 stub)
    custom_ai_endpoint: str | None = None
    custom_ai_api_key: str | None = None
    custom_ai_model: str | None = None

    # --- Transcription ---
    transcription_provider: TranscriptionProviderType = TranscriptionProviderType.NONE
    whisper_api_key: str | None = None
    whisper_model: str = "whisper-1"

    # --- Security ---
    remi_api_key: str | None = None
    remi_cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    remi_max_input_length: int = Field(default=50_000, ge=100, le=200_000)

    # --- Audit ---
    audit_log_enabled: bool = True
    audit_log_backend: str = "sqlite_table"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @field_validator("remi_log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"Log level must be one of {allowed}, got '{v}'")
        return upper

    @field_validator("remi_host")
    @classmethod
    def _warn_bind_all(cls, v: str) -> str:
        if v == "0.0.0.0":  # noqa: S104
            import warnings

            warnings.warn(
                "Binding to 0.0.0.0 exposes REMI to the network. "
                "See SECURITY.md before proceeding.",
                UserWarning,
                stacklevel=2,
            )
        return v

    @model_validator(mode="after")
    def _validate_provider_config(self) -> "Settings":
        """Check that the selected providers have required config."""
        if self.ai_provider == AIProviderType.ANTHROPIC:
            if not self.anthropic_api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic"
                )

        if self.transcription_provider == TranscriptionProviderType.WHISPER_API:
            if not self.whisper_api_key:
                raise ValueError(
                    "WHISPER_API_KEY is required when "
                    "TRANSCRIPTION_PROVIDER=whisper_api. "
                    "Set TRANSCRIPTION_PROVIDER=none to disable audio."
                )

        return self

    def get_cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [o.strip() for o in self.remi_cors_origins.split(",") if o.strip()]


# ============================================================================
# Factory functions
# ============================================================================

_V1_STUBS = {
    "storage": {StorageBackend.DYNAMODB},
    "blob": {BlobBackend.S3},
    "ai": {
        AIProviderType.OPENAI,
        AIProviderType.BEDROCK,
        AIProviderType.CUSTOM,
    },
    "transcription": {TranscriptionProviderType.WHISPER_LOCAL},
}


def _stub_error(category: str, name: str) -> NotImplementedError:
    return NotImplementedError(
        f"{name} {category} adapter is planned for a future release. "
        f"See BUILD_PLAN.md for available options."
    )


def build_storage(settings: Settings) -> StorageProvider:
    """Build the configured storage adapter.

    Returns a StorageProvider instance. Import is deferred to avoid
    pulling adapter dependencies into core.
    """
    backend = settings.storage_backend

    if backend in _V1_STUBS["storage"]:
        raise _stub_error("storage", backend.value)

    if backend == StorageBackend.SQLITE:
        from adapters.storage.sqlite import SQLiteStorage

        return SQLiteStorage(db_path=settings.sqlite_path)

    raise ValueError(f"Unknown storage backend: {backend}")


def build_ai(settings: Settings) -> AIProvider:
    """Build the configured AI provider adapter."""
    provider = settings.ai_provider

    if provider in _V1_STUBS["ai"]:
        raise _stub_error("AI", provider.value)

    if provider == AIProviderType.ANTHROPIC:
        from adapters.ai.anthropic_api import AnthropicAI

        return AnthropicAI(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )

    if provider == AIProviderType.OLLAMA:
        from adapters.ai.ollama import OllamaAI

        return OllamaAI(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )

    raise ValueError(f"Unknown AI provider: {provider}")


def build_blob(settings: Settings) -> BlobProvider:
    """Build the configured blob storage adapter."""
    backend = settings.blob_backend

    if backend in _V1_STUBS["blob"]:
        raise _stub_error("blob", backend.value)

    if backend == BlobBackend.FILESYSTEM:
        from adapters.blob.filesystem import FilesystemBlob

        return FilesystemBlob(
            base_path=settings.blob_filesystem_path,
            max_size_bytes=25 * 1024 * 1024,
        )

    raise ValueError(f"Unknown blob backend: {backend}")


def build_transcription(settings: Settings) -> TranscriptionProvider:
    """Build the configured transcription adapter."""
    provider = settings.transcription_provider

    if provider in _V1_STUBS["transcription"]:
        raise _stub_error("transcription", provider.value)

    if provider == TranscriptionProviderType.NONE:
        from adapters.transcription.none import NoneTranscription

        return NoneTranscription()

    if provider == TranscriptionProviderType.WHISPER_API:
        from adapters.transcription.whisper_api import WhisperAPI

        return WhisperAPI(
            api_key=settings.whisper_api_key,
            model=settings.whisper_model,
        )

    raise ValueError(f"Unknown transcription provider: {provider}")

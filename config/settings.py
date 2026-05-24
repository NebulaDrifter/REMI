"""Settings and adapter factory.

The ONLY module that reads environment variables. Every other module receives
its config via dependency injection from here.

Implementation: Phase 2 of BUILD_PLAN.md.
"""

# TODO (Phase 2): Implement Settings class and adapter factories.
#
# Implementation notes:
# - Use pydantic_settings.BaseSettings
# - Match the env var names in .env.example exactly
# - Provide validators for enum-like fields (STORAGE_BACKEND, AI_PROVIDER, etc.)
# - Factory functions return the configured adapter:
#     - build_storage(settings) -> StorageProvider
#     - build_ai(settings) -> AIProvider
#     - build_transcription(settings) -> TranscriptionProvider
#     - build_blob(settings) -> BlobProvider
# - If a stub adapter is requested (e.g., AI_PROVIDER=openai in v1.0),
#   raise a clear error explaining what's available

from enum import Enum


class StorageBackend(str, Enum):
    SQLITE = "sqlite"
    DYNAMODB = "dynamodb"  # v1.1


class BlobBackend(str, Enum):
    FILESYSTEM = "filesystem"
    S3 = "s3"  # v1.1


class AIProviderType(str, Enum):
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    OPENAI = "openai"  # stub in v1.0
    BEDROCK = "bedrock"  # stub in v1.0
    CUSTOM = "custom"  # stub in v1.0


class TranscriptionProviderType(str, Enum):
    WHISPER_API = "whisper_api"
    WHISPER_LOCAL = "whisper_local"  # stub in v1.0


# TODO: Define the Settings class
# class Settings(BaseSettings): ...

# TODO: Define factory functions
# def build_storage(settings: Settings) -> StorageProvider: ...
# def build_ai(settings: Settings) -> AIProvider: ...
# def build_transcription(settings: Settings) -> TranscriptionProvider: ...
# def build_blob(settings: Settings) -> BlobProvider: ...

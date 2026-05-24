"""Dependency injection for FastAPI routes.

Adapters are built once at startup and stored on app.state.
These functions retrieve them for use in route handlers.
"""

from fastapi import Request

from adapters.ai.base import AIProvider
from adapters.blob.base import BlobProvider
from adapters.storage.base import StorageProvider
from adapters.transcription.base import TranscriptionProvider


def get_storage(request: Request) -> StorageProvider:
    """Get the storage adapter from app state."""
    return request.app.state.storage


def get_ai(request: Request) -> AIProvider:
    """Get the AI provider adapter from app state."""
    return request.app.state.ai


def get_blob(request: Request) -> BlobProvider:
    """Get the blob storage adapter from app state."""
    return request.app.state.blob


def get_transcription(request: Request) -> TranscriptionProvider:
    """Get the transcription adapter from app state."""
    return request.app.state.transcription

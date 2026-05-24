"""Abstract blob storage interface.

For audio files (and potentially other large binary content in v2).
"""

from abc import ABC, abstractmethod
from pathlib import Path


# ============================================================================
# Exceptions
# ============================================================================


class BlobError(Exception):
    """Base exception for blob storage errors."""


class BlobNotFoundError(BlobError):
    """Requested blob doesn't exist."""


class BlobTooLargeError(BlobError):
    """Blob exceeds configured size limit."""


class InvalidKeyError(BlobError):
    """Blob key is invalid (path traversal, illegal chars, etc.)."""


# ============================================================================
# Interface
# ============================================================================


class BlobProvider(ABC):
    """Abstract interface for blob (file) storage.

    Keys are opaque strings. Implementations must:
    - Reject path traversal attempts (../, absolute paths, etc.)
    - Enforce size limits
    - Be safe to call concurrently
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Set up storage (create directories, verify bucket access, etc.).

        Idempotent. Called at app startup.
        """
        ...

    @abstractmethod
    async def write(self, key: str, data: bytes) -> str:
        """Write bytes to storage under the given key.

        Args:
            key: Opaque identifier (e.g., "audio/2026/05/abc123.webm")
            data: Raw bytes

        Returns:
            The key used (may differ from input if normalized)

        Raises:
            InvalidKeyError: Key has path traversal or illegal chars
            BlobTooLargeError: Data exceeds size limit
        """
        ...

    @abstractmethod
    async def read(self, key: str) -> bytes:
        """Read bytes from storage.

        Raises:
            BlobNotFoundError: Key doesn't exist
            InvalidKeyError: Key has path traversal or illegal chars
        """
        ...

    @abstractmethod
    async def get_local_path(self, key: str) -> Path:
        """Return a local filesystem path for the blob.

        For filesystem adapter: the actual path.
        For S3 adapter: downloads to a temp file and returns that path.

        Used by transcription which needs a real file handle.

        Raises:
            BlobNotFoundError: Key doesn't exist
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a blob. No-op if it doesn't exist.

        Raises:
            InvalidKeyError: Key has path traversal or illegal chars
        """
        ...

    @abstractmethod
    async def delete_older_than(self, days: int) -> int:
        """Delete all blobs older than N days. Returns count deleted.

        Used for audio retention enforcement per SECURITY.md.
        """
        ...

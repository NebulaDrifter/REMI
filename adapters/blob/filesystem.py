"""Local filesystem blob adapter.

Stores blobs on local disk. For v1.0 local deployments.
"""

import asyncio
import os
import re
import time
from pathlib import Path

from adapters.blob.base import (
    BlobNotFoundError,
    BlobProvider,
    BlobTooLargeError,
    InvalidKeyError,
)

_VALID_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9/_.\-]+$")


def _validate_key(key: str, base_path: Path) -> Path:
    """Validate and resolve a blob key to a safe filesystem path."""
    if not key or not key.strip():
        raise InvalidKeyError("Blob key must not be empty")

    if ".." in key:
        raise InvalidKeyError("Blob key must not contain '..'")

    if key.startswith("/"):
        raise InvalidKeyError("Blob key must not start with '/'")

    if not _VALID_KEY_PATTERN.match(key):
        raise InvalidKeyError(
            "Blob key contains invalid characters. Allowed: a-z, A-Z, 0-9, /, _, ., -"
        )

    resolved = (base_path / key).resolve()
    if not str(resolved).startswith(str(base_path)):
        raise InvalidKeyError("Blob key resolves outside storage directory")

    return resolved


class FilesystemBlob(BlobProvider):
    """Filesystem implementation of BlobProvider."""

    DEFAULT_MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100MB

    def __init__(
        self,
        base_path: str,
        max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
    ) -> None:
        self.base_path = Path(base_path).resolve()
        self.max_size_bytes = max_size_bytes

    async def initialize(self) -> None:
        """Create base directory with restrictive permissions."""
        await asyncio.to_thread(self.base_path.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(os.chmod, self.base_path, 0o700)

    async def write(self, key: str, data: bytes) -> str:
        """Write bytes to disk under the given key."""
        if len(data) > self.max_size_bytes:
            raise BlobTooLargeError(
                f"Blob size {len(data)} exceeds limit {self.max_size_bytes}"
            )

        path = _validate_key(key, self.base_path)
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, data)
        await asyncio.to_thread(os.chmod, path, 0o600)
        return key

    async def read(self, key: str) -> bytes:
        """Read bytes from disk."""
        path = _validate_key(key, self.base_path)
        if not await asyncio.to_thread(path.exists):
            raise BlobNotFoundError(f"Blob not found: {key}")
        return await asyncio.to_thread(path.read_bytes)

    async def get_local_path(self, key: str) -> Path:
        """Return the local filesystem path for a blob."""
        path = _validate_key(key, self.base_path)
        if not await asyncio.to_thread(path.exists):
            raise BlobNotFoundError(f"Blob not found: {key}")
        return path

    async def delete(self, key: str) -> None:
        """Delete a blob. No-op if it doesn't exist."""
        path = _validate_key(key, self.base_path)
        if await asyncio.to_thread(path.exists):
            await asyncio.to_thread(path.unlink)

    async def delete_older_than(self, days: int) -> int:
        """Delete all blobs older than N days. Returns count deleted."""
        cutoff = time.time() - (days * 86400)
        deleted = 0

        def _walk_and_delete() -> int:
            count = 0
            for file_path in self.base_path.rglob("*"):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff:
                    file_path.unlink()
                    count += 1
            return count

        deleted = await asyncio.to_thread(_walk_and_delete)
        return deleted

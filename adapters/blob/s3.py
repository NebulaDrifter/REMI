"""S3 blob adapter.

Cloud implementation of BlobProvider. Uses S3 for audio file storage.

Implementation: v1.1 (Phase 12 of BUILD_PLAN.md). DO NOT IMPLEMENT IN v1.0.
"""

from pathlib import Path

from adapters.blob.base import BlobProvider


class S3Blob(BlobProvider):
    """S3 implementation of BlobProvider. Stub — ships in v1.1."""

    def __init__(self, **kwargs) -> None:
        raise NotImplementedError(
            "S3 adapter ships in v1.1. See DECISIONS.md item 10."
        )

    async def initialize(self) -> None:
        raise NotImplementedError("v1.1")

    async def write(self, key: str, data: bytes) -> str:
        raise NotImplementedError("v1.1")

    async def read(self, key: str) -> bytes:
        raise NotImplementedError("v1.1")

    async def get_local_path(self, key: str) -> Path:
        raise NotImplementedError("v1.1")

    async def delete(self, key: str) -> None:
        raise NotImplementedError("v1.1")

    async def delete_older_than(self, days: int) -> int:
        raise NotImplementedError("v1.1 — note: S3 lifecycle rules typically handle this server-side")

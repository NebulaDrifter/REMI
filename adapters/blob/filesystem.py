"""Local filesystem blob adapter.

Stores blobs on local disk. For v1.0 local deployments.

Implementation: Phase 4 of BUILD_PLAN.md.
"""

# TODO (Phase 4): Implement FilesystemBlob(BlobProvider).
#
# Implementation notes:
# - Base directory configurable (BLOB_FILESYSTEM_PATH env var)
# - Create base dir on initialize() if missing, with mode 0o700
# - Sanitize keys aggressively:
#   - Reject any key containing ".." or starting with "/"
#   - Reject any key with characters outside [a-zA-Z0-9/_.-]
#   - Use os.path.commonpath to verify resolved path is inside base dir
# - File permissions: 0o600 on every written file
# - Use aiofiles for async I/O
# - delete_older_than walks the tree, checks mtime, deletes old files

from pathlib import Path

from adapters.blob.base import BlobProvider


class FilesystemBlob(BlobProvider):
    """Filesystem implementation of BlobProvider.

    TODO: Implement in Phase 4.
    """

    DEFAULT_MAX_SIZE_BYTES = 100 * 1024 * 1024  # 100MB

    def __init__(
        self,
        base_path: str,
        max_size_bytes: int = DEFAULT_MAX_SIZE_BYTES,
    ) -> None:
        self.base_path = Path(base_path).resolve()
        self.max_size_bytes = max_size_bytes

    async def initialize(self) -> None:
        raise NotImplementedError("Phase 4: create base dir with 0o700")

    async def write(self, key: str, data: bytes) -> str:
        raise NotImplementedError("Phase 4: sanitize key, write with 0o600")

    async def read(self, key: str) -> bytes:
        raise NotImplementedError("Phase 4")

    async def get_local_path(self, key: str) -> Path:
        raise NotImplementedError("Phase 4")

    async def delete(self, key: str) -> None:
        raise NotImplementedError("Phase 4")

    async def delete_older_than(self, days: int) -> int:
        raise NotImplementedError("Phase 4")

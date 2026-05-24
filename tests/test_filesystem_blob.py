"""Tests for filesystem blob adapter — Phase 4."""

import os
import time

import pytest

from adapters.blob.base import BlobNotFoundError, BlobTooLargeError, InvalidKeyError
from adapters.blob.filesystem import FilesystemBlob


@pytest.fixture
async def blob(tmp_path):
    """Provide an initialized filesystem blob adapter."""
    b = FilesystemBlob(
        base_path=str(tmp_path / "blobs"),
        max_size_bytes=1024,
    )
    await b.initialize()
    yield b


class TestInitialize:
    async def test_creates_directory(self, tmp_path):
        base = tmp_path / "new_dir" / "blobs"
        b = FilesystemBlob(base_path=str(base))
        await b.initialize()
        assert base.exists()
        assert oct(base.stat().st_mode & 0o777) == "0o700"


class TestWrite:
    async def test_write_and_read(self, blob):
        data = b"hello audio data"
        key = await blob.write("audio/test.webm", data)
        assert key == "audio/test.webm"

        result = await blob.read("audio/test.webm")
        assert result == data

    async def test_file_permissions(self, blob):
        await blob.write("test.webm", b"data")
        path = await blob.get_local_path("test.webm")
        mode = oct(path.stat().st_mode & 0o777)
        assert mode == "0o600"

    async def test_creates_subdirectories(self, blob):
        await blob.write("audio/2026/05/test.webm", b"data")
        result = await blob.read("audio/2026/05/test.webm")
        assert result == b"data"

    async def test_too_large_raises(self, blob):
        data = b"x" * 2048
        with pytest.raises(BlobTooLargeError, match="exceeds limit"):
            await blob.write("big.webm", data)


class TestKeyValidation:
    async def test_path_traversal_rejected(self, blob):
        with pytest.raises(InvalidKeyError, match="\\.\\."):
            await blob.write("../escape.txt", b"bad")

    async def test_absolute_path_rejected(self, blob):
        with pytest.raises(InvalidKeyError, match="start with"):
            await blob.write("/etc/passwd", b"bad")

    async def test_empty_key_rejected(self, blob):
        with pytest.raises(InvalidKeyError, match="empty"):
            await blob.write("", b"data")

    async def test_special_chars_rejected(self, blob):
        with pytest.raises(InvalidKeyError, match="invalid characters"):
            await blob.write("file name!.webm", b"data")

    async def test_valid_key_accepted(self, blob):
        await blob.write("audio/2026-05/test_file.webm", b"data")
        result = await blob.read("audio/2026-05/test_file.webm")
        assert result == b"data"


class TestRead:
    async def test_missing_blob_raises(self, blob):
        with pytest.raises(BlobNotFoundError):
            await blob.read("nonexistent.webm")


class TestGetLocalPath:
    async def test_returns_path(self, blob):
        await blob.write("test.webm", b"data")
        path = await blob.get_local_path("test.webm")
        assert path.exists()
        assert path.read_bytes() == b"data"

    async def test_missing_raises(self, blob):
        with pytest.raises(BlobNotFoundError):
            await blob.get_local_path("missing.webm")


class TestDelete:
    async def test_delete_existing(self, blob):
        await blob.write("test.webm", b"data")
        await blob.delete("test.webm")
        with pytest.raises(BlobNotFoundError):
            await blob.read("test.webm")

    async def test_delete_nonexistent_is_noop(self, blob):
        await blob.delete("nonexistent.webm")


class TestDeleteOlderThan:
    async def test_deletes_old_files(self, blob):
        await blob.write("old.webm", b"old data")
        path = await blob.get_local_path("old.webm")
        old_time = time.time() - (8 * 86400)
        os.utime(path, (old_time, old_time))

        await blob.write("new.webm", b"new data")

        deleted = await blob.delete_older_than(days=7)
        assert deleted == 1

        with pytest.raises(BlobNotFoundError):
            await blob.read("old.webm")
        result = await blob.read("new.webm")
        assert result == b"new data"

    async def test_no_old_files(self, blob):
        await blob.write("recent.webm", b"data")
        deleted = await blob.delete_older_than(days=7)
        assert deleted == 0

"""Tests for the Ollama model management adapter."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from adapters.ai.base import AIProviderError
from adapters.ai.ollama_manager import OllamaManager, PullProgress


def _response(data: dict | str, status_code: int = 200) -> httpx.Response:
    body = json.dumps(data) if isinstance(data, dict) else data
    return httpx.Response(
        status_code=status_code,
        content=body.encode(),
        request=httpx.Request("GET", "http://test/api/tags"),
    )


class TestParsePullLine:
    def test_progress_line(self):
        p = OllamaManager._parse_pull_line(
            json.dumps({"status": "downloading", "completed": 50, "total": 100})
        )
        assert p.status == "downloading"
        assert p.percent == 50
        assert not p.done

    def test_success_line(self):
        p = OllamaManager._parse_pull_line(json.dumps({"status": "success"}))
        assert p.done

    def test_error_line(self):
        p = OllamaManager._parse_pull_line(json.dumps({"error": "model not found"}))
        assert p.error == "model not found"
        assert p.done

    def test_garbage_line(self):
        p = OllamaManager._parse_pull_line("not json")
        assert p.error == "not json"
        assert p.done


class TestPullProgress:
    def test_percent_unknown_total(self):
        assert PullProgress(status="x", completed=10, total=0).percent == 0

    def test_percent_caps_at_100(self):
        assert PullProgress(status="x", completed=200, total=100).percent == 100


class TestListModels:
    async def test_lists_and_sorts(self):
        mgr = OllamaManager()
        mgr._client.get = AsyncMock(
            return_value=_response(
                {
                    "models": [
                        {"name": "qwen2.5:7b", "size": 4_700_000_000},
                        {"name": "llama3.2:3b", "size": 2_000_000_000},
                    ]
                }
            )
        )
        models = await mgr.list_models()
        assert [m.name for m in models] == ["llama3.2:3b", "qwen2.5:7b"]
        assert models[0].size_bytes == 2_000_000_000

    async def test_connect_error_raises(self):
        mgr = OllamaManager()
        mgr._client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(AIProviderError, match="Cannot connect"):
            await mgr.list_models()


class TestDeleteModel:
    async def test_delete_ok(self):
        mgr = OllamaManager()
        mgr._client.request = AsyncMock(return_value=_response({}, status_code=200))
        await mgr.delete_model("llama3.2:3b")  # no raise

    async def test_delete_missing_raises(self):
        mgr = OllamaManager()
        mgr._client.request = AsyncMock(return_value=_response({}, status_code=404))
        with pytest.raises(AIProviderError, match="not installed"):
            await mgr.delete_model("ghost")


class _FakeStream:
    """Async context manager mimicking httpx streaming response."""

    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def aiter_lines(self):
        for line in self._lines:
            yield line

    async def aread(self):
        return b"error body"


class TestPullModel:
    async def test_streams_progress(self):
        mgr = OllamaManager()
        lines = [
            json.dumps({"status": "pulling manifest"}),
            json.dumps({"status": "downloading", "completed": 5, "total": 10}),
            json.dumps({"status": "success"}),
        ]
        mgr._client.stream = lambda *a, **k: _FakeStream(lines)

        updates = [p async for p in mgr.pull_model("llama3.2:3b")]
        assert updates[-1].done
        assert updates[1].percent == 50

    async def test_non_200_yields_error(self):
        mgr = OllamaManager()
        mgr._client.stream = lambda *a, **k: _FakeStream([], status_code=500)
        updates = [p async for p in mgr.pull_model("bad")]
        assert updates[-1].error is not None
        assert updates[-1].done

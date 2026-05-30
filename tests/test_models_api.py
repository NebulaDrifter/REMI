"""Tests for the local model management API (Ollama hot-swap)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from adapters.ai.ollama import OllamaAI
from adapters.ai.ollama_manager import OllamaModel, PullProgress
from adapters.storage.sqlite import SQLiteStorage
from api.main import app
from api.routes.models import ACTIVE_MODEL_KEY


@pytest.fixture
async def storage(tmp_path):
    s = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def manager():
    m = MagicMock()
    m.base_url = "http://ollama:11434"
    m.list_models = AsyncMock(
        return_value=[
            OllamaModel(name="llama3.2:3b", size_bytes=2_000_000_000),
            OllamaModel(name="qwen2.5:7b", size_bytes=4_700_000_000),
        ]
    )
    m.delete_model = AsyncMock()
    return m


@pytest.fixture
async def client(storage, manager):
    app.state.storage = storage
    app.state.ollama_manager = manager
    app.state.pull_jobs = {}
    app.state.ai = MagicMock(model="llama3.2:3b")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestListModels:
    async def test_list(self, client):
        resp = await client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] == "llama3.2:3b"
        assert {m["name"] for m in data["installed"]} == {"llama3.2:3b", "qwen2.5:7b"}
        assert data["suggested"]

    async def test_409_when_no_manager(self, client):
        app.state.ollama_manager = None
        resp = await client.get("/api/models")
        assert resp.status_code == 409


class TestSetActive:
    async def test_hot_swap_replaces_adapter_and_persists(self, client, storage):
        resp = await client.post("/api/models/active", json={"name": "qwen2.5:7b"})
        assert resp.status_code == 200
        assert isinstance(app.state.ai, OllamaAI)
        assert app.state.ai.model == "qwen2.5:7b"
        # Persisted for next startup
        assert await storage.get_app_config(ACTIVE_MODEL_KEY) == "qwen2.5:7b"

    async def test_rejects_uninstalled_model(self, client):
        resp = await client.post("/api/models/active", json={"name": "ghost:1b"})
        assert resp.status_code == 400

    async def test_rejects_bad_name(self, client):
        resp = await client.post("/api/models/active", json={"name": "bad name!!"})
        assert resp.status_code == 422


class TestDelete:
    async def test_delete_non_active(self, client, manager):
        resp = await client.delete("/api/models/qwen2.5:7b")
        assert resp.status_code == 200
        manager.delete_model.assert_awaited_once()

    async def test_cannot_delete_active(self, client):
        resp = await client.delete("/api/models/llama3.2:3b")
        assert resp.status_code == 409


async def _fake_pull(name):
    yield PullProgress(status="downloading", completed=5, total=10)
    yield PullProgress(status="success", done=True)


class TestPull:
    async def test_pull_starts_and_completes(self, client, manager):
        manager.pull_model = _fake_pull
        resp = await client.post("/api/models/pull", json={"name": "phi3.5"})
        assert resp.status_code == 202

        # Let the background task drain
        for _ in range(20):
            await asyncio.sleep(0.01)
            status = await client.get("/api/models/pull/status?name=phi3.5")
            if status.json().get("done"):
                break
        assert status.json()["done"] is True

    async def test_status_404_for_unknown(self, client):
        resp = await client.get("/api/models/pull/status?name=nope")
        assert resp.status_code == 404

"""Smoke tests for the FastAPI application — Phase 7."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from adapters.storage.sqlite import SQLiteStorage
from api.main import app
from core.models import (
    ExtractionResult,
    Fact,
    FactCategory,
    InteractionType,
)


@pytest.fixture
async def storage(tmp_path):
    """Real SQLite storage for integration tests."""
    s = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def mock_ai():
    """Mock AI provider."""
    ai = MagicMock()
    ai.extract_structured = AsyncMock(
        return_value=ExtractionResult(
            person_name="Jerry",
            interaction_type=InteractionType.CASUAL,
            summary="Brief chat about music",
            facts=[Fact(category=FactCategory.INTEREST, content="likes Fall Out Boy")],
            tags_added=["music-fan"],
            loops=[],
        )
    )
    ai.generate_text = AsyncMock(return_value="Jerry is a colleague at Acme.")
    return ai


@pytest.fixture
def mock_blob():
    """Mock blob provider."""
    blob = MagicMock()
    blob.write = AsyncMock(return_value="audio/test.webm")
    blob.get_local_path = AsyncMock()
    return blob


@pytest.fixture
def mock_transcription():
    """Mock transcription provider."""
    t = MagicMock()
    t.transcribe = AsyncMock(return_value="Jerry likes Fall Out Boy")
    return t


@pytest.fixture
async def client(storage, mock_ai, mock_blob, mock_transcription):
    """Configured test client with real storage and mocked AI/blob."""
    app.state.storage = storage
    app.state.ai = mock_ai
    app.state.blob = mock_blob
    app.state.transcription = mock_transcription
    app.state.settings = MagicMock()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_jerry(client) -> dict:
    """Helper to create Jerry via API."""
    resp = await client.post(
        "/people",
        json={
            "name": "Jerry Brown",
            "company": "Acme",
            "relationship_type": "colleague",
            "tags": ["music-fan"],
        },
    )
    assert resp.status_code == 201
    return resp.json()


class TestHealth:
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestPeople:
    async def test_create_person(self, client):
        data = await _create_jerry(client)
        assert data["name"] == "Jerry Brown"
        assert data["company"] == "Acme"

    async def test_list_people(self, client):
        await _create_jerry(client)
        resp = await client.get("/people")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_get_person(self, client):
        jerry = await _create_jerry(client)
        resp = await client.get(f"/people/{jerry['person_id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Jerry Brown"

    async def test_get_person_not_found(self, client):
        resp = await client.get("/people/nonexistent")
        assert resp.status_code == 404

    async def test_search_people(self, client):
        await _create_jerry(client)
        resp = await client.get("/people/search?name=jerry")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_update_person(self, client):
        jerry = await _create_jerry(client)
        resp = await client.patch(
            f"/people/{jerry['person_id']}",
            json={
                "name": "Jerry Brown",
                "company": "NewCo",
                "relationship_type": "colleague",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["company"] == "NewCo"

    async def test_delete_person(self, client):
        jerry = await _create_jerry(client)
        resp = await client.delete(f"/people/{jerry['person_id']}")
        assert resp.status_code == 204

        resp = await client.get(f"/people/{jerry['person_id']}")
        assert resp.status_code == 404


class TestInteractions:
    async def test_submit_text(self, client):
        resp = await client.post(
            "/interactions/text",
            json={
                "raw_input": "Water cooler with Jerry, he likes Fall Out Boy",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["extraction"]["person_name"] == "Jerry"
        assert data["person_resolution"]["status"] == "needs_clarification"

    async def test_submit_text_matches_existing(self, client):
        await _create_jerry(client)
        resp = await client.post(
            "/interactions/text",
            json={"raw_input": "Lunch with Jerry"},
        )
        data = resp.json()
        assert data["person_resolution"]["status"] == "matched"

    async def test_confirm_save(self, client):
        jerry = await _create_jerry(client)
        extraction = {
            "person_name": "Jerry",
            "interaction_type": "casual",
            "summary": "Brief chat about music",
            "facts": [{"category": "interest", "content": "likes Fall Out Boy"}],
            "tags_added": ["music-fan"],
            "loops": [
                {"description": "Jerry sending album link", "due_date": "2026-05-29"}
            ],
        }
        resp = await client.post(
            "/interactions/confirm",
            json={
                "person_id": jerry["person_id"],
                "extraction": extraction,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "interaction_id" in data
        assert len(data["loop_ids"]) == 1

    async def test_list_interactions(self, client):
        jerry = await _create_jerry(client)
        extraction = {
            "person_name": "Jerry",
            "interaction_type": "casual",
            "summary": "Chat",
            "facts": [],
            "tags_added": [],
            "loops": [],
        }
        await client.post(
            "/interactions/confirm",
            json={"person_id": jerry["person_id"], "extraction": extraction},
        )
        resp = await client.get(f"/interactions/{jerry['person_id']}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestLoops:
    async def test_create_loop(self, client):
        jerry = await _create_jerry(client)
        resp = await client.post(
            f"/people/{jerry['person_id']}/loops",
            json={"description": "Send Jerry the report", "due_date": "2026-06-01"},
        )
        assert resp.status_code == 201
        assert resp.json()["description"] == "Send Jerry the report"

    async def test_update_loop_status(self, client):
        jerry = await _create_jerry(client)
        create_resp = await client.post(
            f"/people/{jerry['person_id']}/loops",
            json={"description": "Follow up"},
        )
        loop = create_resp.json()
        resp = await client.patch(
            f"/loops/{jerry['person_id']}/{loop['loop_id']}",
            json={"status": "done"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"
        assert resp.json()["closed_at"] is not None

    async def test_list_loops(self, client):
        jerry = await _create_jerry(client)
        await client.post(
            f"/people/{jerry['person_id']}/loops",
            json={"description": "Task 1"},
        )
        resp = await client.get(f"/people/{jerry['person_id']}/loops")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


class TestBriefs:
    async def test_generate_brief(self, client):
        jerry = await _create_jerry(client)
        resp = await client.get(f"/people/{jerry['person_id']}/brief")
        assert resp.status_code == 200
        data = resp.json()
        assert data["person_name"] == "Jerry Brown"
        assert "Jerry" in data["brief"]

    async def test_brief_not_found(self, client):
        resp = await client.get("/people/nonexistent/brief")
        assert resp.status_code == 404


class TestValidation:
    async def test_empty_name_rejected(self, client):
        resp = await client.post(
            "/people",
            json={"name": "", "relationship_type": "colleague"},
        )
        assert resp.status_code == 422

    async def test_invalid_relationship_type(self, client):
        resp = await client.post(
            "/people",
            json={"name": "Test", "relationship_type": "enemy"},
        )
        assert resp.status_code == 422

    async def test_empty_interaction_rejected(self, client):
        resp = await client.post(
            "/interactions/text",
            json={"raw_input": ""},
        )
        assert resp.status_code == 422

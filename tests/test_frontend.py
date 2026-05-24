"""Smoke tests for frontend HTML routes — Phase 8."""

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
    RelationshipType,
)


@pytest.fixture
async def storage(tmp_path):
    s = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
def mock_ai():
    ai = MagicMock()
    ai.extract_structured = AsyncMock(
        return_value=ExtractionResult(
            person_name="Jerry",
            interaction_type=InteractionType.CASUAL,
            summary="Chat about music",
            facts=[Fact(category=FactCategory.INTEREST, content="likes Fall Out Boy")],
            tags_added=[],
            loops=[],
        )
    )
    ai.generate_text = AsyncMock(return_value="Jerry is a colleague at Acme.")
    return ai


@pytest.fixture
async def client(storage, mock_ai):
    app.state.storage = storage
    app.state.ai = mock_ai
    app.state.blob = MagicMock()
    app.state.transcription = MagicMock()
    settings = MagicMock()
    settings.remi_deployment = "local"
    settings.storage_backend.value = "sqlite"
    settings.ai_provider.value = "anthropic"
    settings.anthropic_model = "claude-sonnet-4-5"
    settings.blob_backend.value = "filesystem"
    settings.transcription_provider.value = "whisper_api"
    settings.audio_retention_days = 7
    settings.ollama_model = "llama3.1:8b"
    app.state.settings = settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestFrontendPages:
    async def test_capture_page(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "Capture" in resp.text
        assert "raw-input" in resp.text

    async def test_people_list_empty(self, client):
        resp = await client.get("/app/people")
        assert resp.status_code == 200
        assert "People" in resp.text
        assert "No people yet" in resp.text

    async def test_people_list_with_data(self, client, storage):
        from core.models import Person

        await storage.create_person(
            Person(
                name="Jerry Brown",
                name_lower="jerry brown",
                company="Acme",
                relationship_type=RelationshipType.COLLEAGUE,
            )
        )
        resp = await client.get("/app/people")
        assert resp.status_code == 200
        assert "Jerry Brown" in resp.text
        assert "Acme" in resp.text

    async def test_person_detail(self, client, storage):
        from core.models import Person

        person = Person(
            name="Jerry Brown",
            name_lower="jerry brown",
            company="Acme",
            relationship_type=RelationshipType.COLLEAGUE,
        )
        await storage.create_person(person)
        resp = await client.get(f"/app/people/{person.person_id}")
        assert resp.status_code == 200
        assert "Jerry Brown" in resp.text

    async def test_person_not_found(self, client):
        resp = await client.get("/app/people/nonexistent")
        assert resp.status_code == 404

    async def test_brief_page(self, client, storage):
        from core.models import Person

        person = Person(
            name="Jerry Brown",
            name_lower="jerry brown",
            company="Acme",
            relationship_type=RelationshipType.COLLEAGUE,
        )
        await storage.create_person(person)
        resp = await client.get(f"/app/people/{person.person_id}/brief")
        assert resp.status_code == 200
        assert "Jerry" in resp.text
        assert "Copy" in resp.text

    async def test_settings_page(self, client):
        resp = await client.get("/app/settings")
        assert resp.status_code == 200
        assert "Settings" in resp.text
        assert "sqlite" in resp.text
        assert "anthropic" in resp.text

    async def test_search_html(self, client, storage):
        from core.models import Person

        await storage.create_person(
            Person(
                name="Jerry Brown",
                name_lower="jerry brown",
                relationship_type=RelationshipType.COLLEAGUE,
            )
        )
        resp = await client.get("/api/people/search-html?name=jerry")
        assert resp.status_code == 200
        assert "Jerry Brown" in resp.text

    async def test_static_files(self, client):
        resp = await client.get("/static/js/capture.js")
        assert resp.status_code == 200
        assert "capture-form" in resp.text

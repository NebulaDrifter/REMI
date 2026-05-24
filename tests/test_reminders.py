"""Tests for reminders — storage, API, and extraction."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from adapters.storage.base import NotFoundError
from adapters.storage.sqlite import SQLiteStorage
from api.main import app
from core.models import (
    ExtractionResult,
    Fact,
    FactCategory,
    InteractionType,
    Person,
    RelationshipType,
    Reminder,
    ReminderRecurrence,
    ReminderStatus,
)


@pytest.fixture
async def storage(tmp_path):
    s = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    await s.initialize()
    yield s
    await s.close()


async def _make_person(storage) -> Person:
    person = Person(
        name="Jerry Brown",
        name_lower="jerry brown",
        company="Acme",
        relationship_type=RelationshipType.COLLEAGUE,
    )
    return await storage.create_person(person)


def _reminder(person_id: str, **overrides) -> Reminder:
    defaults = {
        "person_id": person_id,
        "title": "Jerry's birthday",
        "date": "06-12",
        "recurrence": ReminderRecurrence.ANNUAL,
    }
    defaults.update(overrides)
    return Reminder(**defaults)


# ============================================================================
# Storage tests
# ============================================================================


class TestReminderStorage:
    async def test_create_and_list(self, storage):
        person = await _make_person(storage)
        reminder = _reminder(person.person_id)
        await storage.create_reminder(reminder)

        results = await storage.list_reminders_for_person(person.person_id)
        assert len(results) == 1
        assert results[0].title == "Jerry's birthday"
        assert results[0].recurrence == ReminderRecurrence.ANNUAL

    async def test_dismiss_reminder(self, storage):
        person = await _make_person(storage)
        reminder = _reminder(person.person_id)
        await storage.create_reminder(reminder)

        dismissed = await storage.dismiss_reminder(
            person.person_id, reminder.reminder_id
        )
        assert dismissed.status == ReminderStatus.DISMISSED

    async def test_dismiss_nonexistent_raises(self, storage):
        with pytest.raises(NotFoundError):
            await storage.dismiss_reminder("no-person", "no-reminder")

    async def test_delete_person_cascades_reminders(self, storage):
        person = await _make_person(storage)
        await storage.create_reminder(_reminder(person.person_id))

        await storage.delete_person(person.person_id)

        results = await storage.list_reminders_for_person(person.person_id)
        assert results == []


class TestUpcomingReminders:
    async def test_annual_upcoming(self, storage):
        person = await _make_person(storage)
        today = datetime.now(UTC).date()
        upcoming_mmdd = (today + timedelta(days=3)).strftime("%m-%d")

        await storage.create_reminder(_reminder(person.person_id, date=upcoming_mmdd))

        results = await storage.list_upcoming_reminders(days=7)
        assert len(results) == 1
        assert results[0].person_name == "Jerry Brown"

    async def test_annual_not_upcoming(self, storage):
        person = await _make_person(storage)
        today = datetime.now(UTC).date()
        far_mmdd = (today + timedelta(days=30)).strftime("%m-%d")

        await storage.create_reminder(_reminder(person.person_id, date=far_mmdd))

        results = await storage.list_upcoming_reminders(days=7)
        assert len(results) == 0

    async def test_once_upcoming(self, storage):
        person = await _make_person(storage)
        today = datetime.now(UTC).date()
        upcoming_iso = (today + timedelta(days=2)).isoformat()

        await storage.create_reminder(
            _reminder(
                person.person_id,
                title="Mike moving",
                date=upcoming_iso,
                recurrence=ReminderRecurrence.ONCE,
            )
        )

        results = await storage.list_upcoming_reminders(days=7)
        assert len(results) == 1

    async def test_overdue_once_appears(self, storage):
        person = await _make_person(storage)
        past_iso = (datetime.now(UTC).date() - timedelta(days=3)).isoformat()

        await storage.create_reminder(
            _reminder(
                person.person_id,
                title="Overdue task",
                date=past_iso,
                recurrence=ReminderRecurrence.ONCE,
            )
        )

        results = await storage.list_upcoming_reminders(days=7)
        assert len(results) == 1
        assert results[0].reminder.title == "Overdue task"

    async def test_dismissed_not_shown(self, storage):
        person = await _make_person(storage)
        today = datetime.now(UTC).date()
        upcoming_mmdd = (today + timedelta(days=2)).strftime("%m-%d")

        reminder = _reminder(person.person_id, date=upcoming_mmdd)
        await storage.create_reminder(reminder)
        await storage.dismiss_reminder(person.person_id, reminder.reminder_id)

        results = await storage.list_upcoming_reminders(days=7)
        assert len(results) == 0


# ============================================================================
# API tests
# ============================================================================


@pytest.fixture
def mock_ai():
    ai = MagicMock()
    ai.extract_structured = AsyncMock(
        return_value=ExtractionResult(
            person_name="Jerry",
            interaction_type=InteractionType.CASUAL,
            summary="Chat",
            facts=[Fact(category=FactCategory.FAMILY, content="birthday June 12")],
            tags_added=[],
            loops=[],
            reminders=[],
        )
    )
    ai.generate_text = AsyncMock(return_value="Brief text")
    return ai


@pytest.fixture
async def client(storage, mock_ai):
    app.state.storage = storage
    app.state.ai = mock_ai
    app.state.blob = MagicMock()
    app.state.transcription = MagicMock()
    app.state.settings = MagicMock()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _create_jerry_api(client) -> dict:
    resp = await client.post(
        "/people",
        json={
            "name": "Jerry Brown",
            "company": "Acme",
            "relationship_type": "colleague",
        },
    )
    return resp.json()


class TestRemindersAPI:
    async def test_create_reminder(self, client):
        jerry = await _create_jerry_api(client)
        resp = await client.post(
            f"/people/{jerry['person_id']}/reminders",
            json={
                "title": "Jerry's birthday",
                "date": "06-12",
                "recurrence": "annual",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "Jerry's birthday"

    async def test_list_reminders(self, client):
        jerry = await _create_jerry_api(client)
        await client.post(
            f"/people/{jerry['person_id']}/reminders",
            json={
                "title": "Birthday",
                "date": "06-12",
                "recurrence": "annual",
            },
        )
        resp = await client.get(f"/people/{jerry['person_id']}/reminders")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    async def test_dismiss_reminder(self, client):
        jerry = await _create_jerry_api(client)
        create_resp = await client.post(
            f"/people/{jerry['person_id']}/reminders",
            json={
                "title": "Birthday",
                "date": "06-12",
                "recurrence": "annual",
            },
        )
        reminder = create_resp.json()
        resp = await client.patch(
            f"/reminders/{jerry['person_id']}/{reminder['reminder_id']}/dismiss"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "dismissed"

    async def test_confirm_saves_reminders(self, client):
        jerry = await _create_jerry_api(client)
        extraction = {
            "person_name": "Jerry",
            "interaction_type": "casual",
            "summary": "Chat about birthday",
            "facts": [],
            "tags_added": [],
            "loops": [],
            "reminders": [
                {
                    "title": "Jerry's birthday",
                    "date": "06-12",
                    "recurrence": "annual",
                }
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
        assert len(resp.json()["reminder_ids"]) == 1

    async def test_upcoming_endpoint(self, client):
        jerry = await _create_jerry_api(client)
        today = datetime.now(UTC).date()
        upcoming = (today + timedelta(days=2)).strftime("%m-%d")
        await client.post(
            f"/people/{jerry['person_id']}/reminders",
            json={
                "title": "Birthday",
                "date": upcoming,
                "recurrence": "annual",
            },
        )
        resp = await client.get("/api/reminders/upcoming")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

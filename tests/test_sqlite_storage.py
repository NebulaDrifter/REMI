"""Tests for SQLite storage adapter — Phase 3."""

import pytest

from adapters.storage.base import AlreadyExistsError, NotFoundError
from adapters.storage.sqlite import SQLiteStorage
from core.models import (
    AuditLogEntry,
    Fact,
    FactCategory,
    Interaction,
    InteractionType,
    LoopStatus,
    OpenLoop,
    Person,
    RelationshipType,
)


@pytest.fixture
async def storage(tmp_path):
    """Provide an initialized SQLite storage with a temp database."""
    db_path = str(tmp_path / "test.db")
    s = SQLiteStorage(db_path=db_path)
    await s.initialize()
    yield s
    await s.close()


def _make_person(**overrides) -> Person:
    defaults = {
        "name": "Jerry Brown",
        "name_lower": "jerry brown",
        "relationship_type": RelationshipType.COLLEAGUE,
        "company": "Acme",
        "tags": {"music-fan"},
    }
    defaults.update(overrides)
    return Person(**defaults)


def _make_interaction(person_id: str, **overrides) -> Interaction:
    defaults = {
        "person_id": person_id,
        "date": "2026-05-24T14:25:00Z",
        "interaction_type": InteractionType.CASUAL,
        "raw_input": "Water cooler with Jerry, he likes Fall Out Boy",
        "extracted_summary": "Brief hallway chat about music",
        "facts": [Fact(category=FactCategory.INTEREST, content="likes Fall Out Boy")],
        "tags_added": ["music-fan"],
    }
    defaults.update(overrides)
    return Interaction(**defaults)


def _make_loop(person_id: str, **overrides) -> OpenLoop:
    defaults = {
        "person_id": person_id,
        "description": "Jerry sending album link",
        "due_date": "2026-05-29",
        "status": LoopStatus.OPEN,
    }
    defaults.update(overrides)
    return OpenLoop(**defaults)


# ============================================================================
# People
# ============================================================================


class TestCreatePerson:
    async def test_create_and_retrieve(self, storage):
        person = _make_person()
        created = await storage.create_person(person)
        assert created.person_id == person.person_id

        fetched = await storage.get_person(person.person_id)
        assert fetched is not None
        assert fetched.name == "Jerry Brown"
        assert fetched.company == "Acme"
        assert fetched.relationship_type == RelationshipType.COLLEAGUE
        assert "music-fan" in fetched.tags

    async def test_duplicate_raises(self, storage):
        person = _make_person()
        await storage.create_person(person)
        with pytest.raises(AlreadyExistsError):
            await storage.create_person(person)


class TestFindPeopleByName:
    async def test_case_insensitive_search(self, storage):
        person = _make_person(name="Jerry Brown", name_lower="jerry brown")
        await storage.create_person(person)
        results = await storage.find_people_by_name("JERRY")
        assert len(results) == 1
        assert results[0].name == "Jerry Brown"

    async def test_partial_match(self, storage):
        person = _make_person(name="Jerry Brown", name_lower="jerry brown")
        await storage.create_person(person)
        results = await storage.find_people_by_name("jerr")
        assert len(results) == 1

    async def test_no_match_returns_empty(self, storage):
        await storage.create_person(_make_person())
        results = await storage.find_people_by_name("Sarah")
        assert results == []


class TestListPeople:
    async def test_list_with_pagination(self, storage):
        for i in range(5):
            await storage.create_person(
                _make_person(name=f"Person {i}", name_lower=f"person {i}")
            )
        page1 = await storage.list_people(limit=3, offset=0)
        page2 = await storage.list_people(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2


class TestUpdatePerson:
    async def test_update_fields(self, storage):
        person = _make_person()
        await storage.create_person(person)
        person.company = "NewCo"
        person.tags.add("outdoorsy")
        updated = await storage.update_person(person)
        assert updated.company == "NewCo"
        assert "outdoorsy" in updated.tags

    async def test_update_nonexistent_raises(self, storage):
        person = _make_person()
        with pytest.raises(NotFoundError):
            await storage.update_person(person)


class TestDeletePerson:
    async def test_delete_cascades(self, storage):
        person = _make_person()
        await storage.create_person(person)
        await storage.create_interaction(_make_interaction(person.person_id))
        await storage.create_open_loop(_make_loop(person.person_id))

        await storage.delete_person(person.person_id)

        assert await storage.get_person(person.person_id) is None
        assert await storage.list_interactions_for_person(person.person_id) == []
        assert await storage.list_open_loops_for_person(person.person_id) == []

    async def test_delete_nonexistent_raises(self, storage):
        with pytest.raises(NotFoundError):
            await storage.delete_person("nonexistent-id")


# ============================================================================
# Interactions
# ============================================================================


class TestInteractions:
    async def test_create_and_list(self, storage):
        person = _make_person()
        await storage.create_person(person)

        i1 = _make_interaction(person.person_id, raw_input="First chat")
        i2 = _make_interaction(person.person_id, raw_input="Second chat")
        await storage.create_interaction(i1)
        await storage.create_interaction(i2)

        results = await storage.list_interactions_for_person(person.person_id)
        assert len(results) == 2
        assert results[0].interaction_id > results[1].interaction_id

    async def test_get_specific_interaction(self, storage):
        person = _make_person()
        await storage.create_person(person)
        interaction = _make_interaction(person.person_id)
        await storage.create_interaction(interaction)

        fetched = await storage.get_interaction(
            person.person_id, interaction.interaction_id
        )
        assert fetched is not None
        assert fetched.raw_input == interaction.raw_input
        assert len(fetched.facts) == 1
        assert fetched.facts[0].content == "likes Fall Out Boy"
        assert fetched.tags_added == ["music-fan"]

    async def test_get_nonexistent_returns_none(self, storage):
        result = await storage.get_interaction("no-person", "no-interaction")
        assert result is None


# ============================================================================
# Open Loops
# ============================================================================


class TestOpenLoops:
    async def test_create_and_list_for_person(self, storage):
        person = _make_person()
        await storage.create_person(person)
        loop = _make_loop(person.person_id)
        await storage.create_open_loop(loop)

        results = await storage.list_open_loops_for_person(person.person_id)
        assert len(results) == 1
        assert results[0].description == "Jerry sending album link"

    async def test_update_status_sets_closed_at(self, storage):
        person = _make_person()
        await storage.create_person(person)
        loop = _make_loop(person.person_id)
        await storage.create_open_loop(loop)

        loop.status = LoopStatus.DONE
        updated = await storage.update_open_loop(loop)
        assert updated.status == LoopStatus.DONE
        assert updated.closed_at is not None

    async def test_dropped_status_sets_closed_at(self, storage):
        person = _make_person()
        await storage.create_person(person)
        loop = _make_loop(person.person_id)
        await storage.create_open_loop(loop)

        loop.status = LoopStatus.DROPPED
        updated = await storage.update_open_loop(loop)
        assert updated.status == LoopStatus.DROPPED
        assert updated.closed_at is not None

    async def test_update_nonexistent_raises(self, storage):
        loop = _make_loop("no-person")
        with pytest.raises(NotFoundError):
            await storage.update_open_loop(loop)

    async def test_list_by_status_with_due_before(self, storage):
        person = _make_person()
        await storage.create_person(person)

        loop1 = _make_loop(person.person_id, due_date="2026-05-28")
        loop2 = _make_loop(person.person_id, due_date="2026-06-15")
        await storage.create_open_loop(loop1)
        await storage.create_open_loop(loop2)

        due_soon = await storage.list_open_loops_by_status(
            LoopStatus.OPEN, due_before="2026-05-31"
        )
        assert len(due_soon) == 1
        assert due_soon[0].due_date == "2026-05-28"

    async def test_list_by_status_no_filter(self, storage):
        person = _make_person()
        await storage.create_person(person)
        await storage.create_open_loop(_make_loop(person.person_id))

        results = await storage.list_open_loops_by_status(LoopStatus.OPEN)
        assert len(results) == 1


# ============================================================================
# Audit Log
# ============================================================================


class TestAuditLog:
    async def test_write_and_list(self, storage):
        entry = AuditLogEntry(
            actor="single_user_mode",
            action="create_person",
            resource_id="person-123",
            source="api",
        )
        await storage.write_audit_entry(entry)

        entries = await storage.list_audit_entries()
        assert len(entries) == 1
        assert entries[0].action == "create_person"

    async def test_filter_by_action(self, storage):
        e1 = AuditLogEntry(
            actor="single_user_mode",
            action="create_person",
            resource_id="p1",
            source="api",
        )
        e2 = AuditLogEntry(
            actor="single_user_mode",
            action="update_person",
            resource_id="p1",
            source="api",
        )
        await storage.write_audit_entry(e1)
        await storage.write_audit_entry(e2)

        results = await storage.list_audit_entries(action="create_person")
        assert len(results) == 1

    async def test_filter_by_actor(self, storage):
        entry = AuditLogEntry(
            actor="test_user",
            action="create_person",
            resource_id="p1",
            source="api",
        )
        await storage.write_audit_entry(entry)

        results = await storage.list_audit_entries(actor="test_user")
        assert len(results) == 1
        results = await storage.list_audit_entries(actor="other_user")
        assert len(results) == 0


# ============================================================================
# Jerry walkthrough — end-to-end
# ============================================================================


class TestJerryWalkthrough:
    """The canonical example from DATA_MODEL.md."""

    async def test_full_jerry_flow(self, storage):
        jerry = Person(
            name="Jerry Brown",
            name_lower="jerry brown",
            company="Acme",
            relationship_type=RelationshipType.COLLEAGUE,
            tags={"music-fan"},
        )
        await storage.create_person(jerry)

        interaction = Interaction(
            person_id=jerry.person_id,
            date="2026-05-24T14:25:00Z",
            interaction_type=InteractionType.CASUAL,
            raw_input=(
                "Water cooler with Jerry, he likes Fall Out Boy"
                " and said he'd send me the new album link by Friday."
            ),
            extracted_summary=(
                "Brief hallway chat about music; Jerry mentioned a new album"
            ),
            facts=[Fact(category=FactCategory.INTEREST, content="likes Fall Out Boy")],
            tags_added=["music-fan"],
        )
        await storage.create_interaction(interaction)

        loop = OpenLoop(
            person_id=jerry.person_id,
            description="Jerry sending album link",
            due_date="2026-05-29",
            status=LoopStatus.OPEN,
            source_interaction_id=interaction.interaction_id,
        )
        await storage.create_open_loop(loop)

        found = await storage.find_people_by_name("jerry")
        assert len(found) == 1
        assert found[0].name == "Jerry Brown"

        interactions = await storage.list_interactions_for_person(jerry.person_id)
        assert len(interactions) == 1
        assert interactions[0].facts[0].content == "likes Fall Out Boy"

        loops = await storage.list_open_loops_for_person(jerry.person_id)
        assert len(loops) == 1
        assert loops[0].description == "Jerry sending album link"
        assert loops[0].status == LoopStatus.OPEN

        due_this_week = await storage.list_open_loops_by_status(
            LoopStatus.OPEN, due_before="2026-05-31"
        )
        assert len(due_this_week) == 1

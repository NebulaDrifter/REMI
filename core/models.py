"""Pydantic models for REMI's core data types.

These are the authoritative shapes for People, Interactions, OpenLoops, and the
structured extraction output from AI providers. All adapters serialize to/from
these models — no raw dicts allowed in business logic.

See DATA_MODEL.md for full schema documentation including the Jerry walkthrough.
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from ulid import ULID


# ============================================================================
# Enums
# ============================================================================


class RelationshipType(str, Enum):
    """Relationship category for a Person."""

    INVESTOR = "investor"
    FOUNDER = "founder"
    COLLEAGUE = "colleague"
    FRIEND = "friend"
    PROSPECT = "prospect"
    ADVISOR = "advisor"
    CLIENT = "client"
    FAMILY = "family"
    OTHER = "other"


class InteractionType(str, Enum):
    """Kind of interaction that occurred."""

    MEETING = "meeting"
    CALL = "call"
    CASUAL = "casual"  # water cooler, hallway, social
    MESSAGE = "message"  # chat, DM, SMS
    EMAIL = "email"
    OBSERVATION = "observation"  # learned secondhand, no direct interaction
    OTHER = "other"


class FactCategory(str, Enum):
    """Category for a fact extracted from an interaction."""

    INTEREST = "interest"
    PREFERENCE = "preference"
    CONTEXT = "context"
    FAMILY = "family"
    WORK = "work"
    HEALTH = "health"
    OPINION = "opinion"
    OTHER = "other"


class LoopStatus(str, Enum):
    """Status of an open loop (commitment)."""

    OPEN = "open"
    DONE = "done"
    DROPPED = "dropped"


# ============================================================================
# Core entities — what gets stored
# ============================================================================


def _now() -> str:
    """Current UTC time as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _ulid() -> str:
    """Generate a new ULID as a string."""
    return str(ULID())


class Fact(BaseModel):
    """A single fact extracted from an interaction.

    Lives inside an Interaction's `facts` list.
    """

    category: FactCategory
    content: str = Field(..., min_length=1, max_length=1000)


class Person(BaseModel):
    """Stable identity record for a person."""

    person_id: str = Field(default_factory=_ulid)
    name: str = Field(..., min_length=1, max_length=200)
    name_lower: str  # Set automatically from name
    company: str | None = Field(None, max_length=200)
    relationship_type: RelationshipType
    tags: set[str] = Field(default_factory=set)
    pronunciation: str | None = Field(None, max_length=100)
    nickname: str | None = Field(None, max_length=100)
    notes: str | None = Field(None, max_length=10_000)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)

    @field_validator("name_lower", mode="before")
    @classmethod
    def _derive_name_lower(cls, v: str | None, info) -> str:
        """Always derive name_lower from name."""
        if "name" in info.data and info.data["name"]:
            return info.data["name"].lower()
        return v or ""


class Interaction(BaseModel):
    """A single conversation, meeting, message, or observation."""

    person_id: str
    interaction_id: str = Field(default_factory=_ulid)
    date: str  # ISO8601 — when the interaction happened
    interaction_type: InteractionType
    raw_input: str = Field(..., min_length=1, max_length=50_000)
    raw_transcript: str | None = Field(None, max_length=200_000)
    audio_blob_key: str | None = Field(None, max_length=500)
    extracted_summary: str = Field(..., min_length=1, max_length=1000)
    facts: list[Fact] = Field(default_factory=list)
    tags_added: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)


class OpenLoop(BaseModel):
    """A commitment between the user and a person."""

    person_id: str
    loop_id: str = Field(default_factory=_ulid)
    description: str = Field(..., min_length=1, max_length=1000)
    due_date: str | None = None  # ISO8601 date, optional
    status: LoopStatus = LoopStatus.OPEN
    source_interaction_id: str | None = None
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)
    closed_at: str | None = None


class AuditLogEntry(BaseModel):
    """A single audit log entry.

    Records that something happened — NOT what was said. Never log raw content.
    See SECURITY.md "Audit Logging" section.
    """

    audit_id: str = Field(default_factory=_ulid)
    actor: str  # user_id or "single_user_mode"
    action: str  # e.g. "create_person", "update_loop_status"
    resource_id: str
    timestamp: str = Field(default_factory=_now)
    source: str  # e.g. "api", "background_job"


# ============================================================================
# Extraction output — what AI providers return
# ============================================================================


class ExtractedLoop(BaseModel):
    """A loop proposed by the AI during extraction.

    Different from OpenLoop because it has no person_id yet — that gets resolved
    after extraction.
    """

    description: str = Field(..., min_length=1, max_length=1000)
    due_date: str | None = None


class ExtractionResult(BaseModel):
    """Structured output from the extraction prompt.

    Every AI provider, regardless of backend, must produce this shape.
    The AIProvider.extract_structured method's response_model parameter
    will typically be this class.
    """

    person_name: str = Field(..., min_length=1, max_length=200)
    interaction_type: InteractionType
    summary: str = Field(..., min_length=1, max_length=1000)
    facts: list[Fact] = Field(default_factory=list)
    tags_added: list[str] = Field(default_factory=list)
    loops: list[ExtractedLoop] = Field(default_factory=list)


# ============================================================================
# API request/response models
# ============================================================================


class PersonResolutionStatus(str, Enum):
    """Result of trying to match an extracted person_name to existing People."""

    MATCHED = "matched"  # Single match found
    AMBIGUOUS = "ambiguous"  # Multiple matches, user must pick
    NEEDS_CLARIFICATION = "needs_clarification"  # No match, prompt for details


class PersonResolution(BaseModel):
    """How we resolved (or didn't) the person referenced in an interaction."""

    status: PersonResolutionStatus
    matched_person: Person | None = None
    candidates: list[Person] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)  # ["last_name", "context"]


class IngestResponse(BaseModel):
    """Response from POST /interactions/text or /interactions/audio."""

    extraction: ExtractionResult
    person_resolution: PersonResolution
    interaction_id: str | None = None  # Only set if interaction was written

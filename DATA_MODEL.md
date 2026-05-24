# Data Model

> **Summary**
> - Three tables: People, Interactions, OpenLoops
> - Relational structure preserves temporal context (facts have dates and sources)
> - Same logical model in SQLite (local) and DynamoDB (cloud) — adapters handle differences
> - Field-by-field schemas below, plus a concrete walkthrough with "Jerry"

---

## Design Philosophy

**Facts are temporal, not eternal.** "Loves fishing" said in March 2024 may be wrong by October 2025. The relational model preserves both facts across time, with sources and dates intact. Claude can then reason about which fact is current.

**Three concepts, three tables:**

| Concept | Table | What it represents |
|---|---|---|
| Identity | `people` | Stable info about a person |
| Events | `interactions` | A conversation, meeting, or observation with extracted facts |
| Commitments | `open_loops` | Things you owe someone or they owe you |

## Table 1: People

Stable identity for each person.

| Field | Type | Required | Notes |
|---|---|---|---|
| `person_id` | string (ULID) | yes | Sortable by creation time |
| `name` | string | yes | Display name |
| `name_lower` | string | yes | Lowercased name for case-insensitive lookup (GSI in DynamoDB) |
| `company` | string | no | Current employer or affiliation |
| `relationship_type` | enum | yes | See enum below |
| `tags` | string set | no | User/Claude-applied tags (e.g., "outdoorsy", "music-fan") |
| `pronunciation` | string | no | Phonetic guide (e.g., "SHAW-na" for Siobhan) |
| `nickname` | string | no | What they go by (e.g., "Dick" for Richard) |
| `notes` | string | no | Freeform context the user wants persistent |
| `created_at` | string (ISO8601) | yes | Record creation |
| `updated_at` | string (ISO8601) | yes | Last modification |

**`relationship_type` enum:**
```
investor | founder | colleague | friend | prospect | advisor | client | family | other
```

The list can grow. Adding values is backward-compatible; removing them requires migration.

**Lookups needed:**
- By `person_id` (primary key)
- By `name_lower` (for "find Jerry")

## Table 2: Interactions

One row per conversation, meeting, message, or observation.

| Field | Type | Required | Notes |
|---|---|---|---|
| `person_id` | string (ULID) | yes | Foreign key to people |
| `interaction_id` | string (ULID) | yes | Naturally time-sortable |
| `date` | string (ISO8601) | yes | When the interaction happened (can be backdated) |
| `interaction_type` | enum | yes | See enum below |
| `raw_input` | string | yes | What the user typed or said |
| `raw_transcript` | string | no | Whisper output for audio interactions |
| `audio_s3_key` | string | no | Pointer to blob storage if audio |
| `extracted_summary` | string | yes | One-sentence summary from Claude |
| `facts` | list[object] | no | Structured facts extracted (see below) |
| `tags_added` | list[string] | no | Tags Claude proposed adding to the Person |
| `created_at` | string (ISO8601) | yes | When the row was written |

**`interaction_type` enum:**
```
meeting | call | casual | message | email | observation | other
```

**`facts` shape:**
```python
[
    {"category": "interest", "content": "likes Fall Out Boy"},
    {"category": "preference", "content": "prefers tea to coffee"},
    {"category": "context", "content": "moving to Denver in March"},
]
```

**`facts.category` enum:**
```
interest | preference | context | family | work | health | opinion | other
```

**Lookups needed:**
- All interactions for a person, newest first: `WHERE person_id = ? ORDER BY interaction_id DESC`
- A specific interaction: `WHERE person_id = ? AND interaction_id = ?`

**Why two date fields:** `date` is when the interaction happened (could be backdated — "I forgot to log my lunch last week"). `created_at` is when the row was written. The brief uses `date`. Debugging uses `created_at`.

## Table 3: OpenLoops

Commitments — things you promised someone or they promised you.

| Field | Type | Required | Notes |
|---|---|---|---|
| `person_id` | string (ULID) | yes | Foreign key to people |
| `loop_id` | string (ULID) | yes | Time-sortable |
| `description` | string | yes | "Intro Jerry to Sarah Chen" |
| `due_date` | string (ISO8601 date) | no | Many loops are open-ended |
| `status` | enum | yes | open / done / dropped |
| `source_interaction_id` | string | no | Which interaction created this loop |
| `created_at` | string (ISO8601) | yes | Record creation |
| `updated_at` | string (ISO8601) | yes | Last modification |
| `closed_at` | string (ISO8601) | no | Null until status changes |

**`status` enum:**
```
open | done | dropped
```

`dropped` is for loops that just die — "let's grab coffee" never followed up. Not a lie ("done"), not noise ("open forever"). Honest.

**Lookups needed:**
- All loops for a person: `WHERE person_id = ?`
- All open loops due this week (across all people): `WHERE status = "open" AND due_date <= ?`

In DynamoDB, that second query becomes a GSI on `status + due_date`. In SQLite, it's an index on `(status, due_date)`.

---

## Concrete Walkthrough: Jerry

This is the canonical example. Use it to sanity-check any design changes.

### Step 1: Capture

User says (voice or text):
> *"Water cooler with Jerry, he likes Fall Out Boy and said he'd send me the new album link by Friday."*

### Step 2: Extraction

The extraction Lambda hands the input to the AI provider with the extraction prompt. The provider returns structured JSON:

```json
{
  "person_name": "Jerry",
  "interaction_type": "casual",
  "summary": "Brief hallway chat about music; Jerry mentioned a new album",
  "facts": [
    {"category": "interest", "content": "likes Fall Out Boy"}
  ],
  "tags_added": ["music-fan"],
  "loops": [
    {
      "description": "Jerry sending album link",
      "due_date": "2026-05-29"
    }
  ]
}
```

### Step 3: Person Resolution

The Lambda checks the people table for "jerry" (case-insensitive). Three possible outcomes:

| Outcome | Response |
|---|---|
| **No Jerry exists** | Return `{status: "needs_clarification", missing: ["last_name", "context"]}` — UI prompts the user |
| **One Jerry** | Proceed with that `person_id` |
| **Multiple Jerrys** | Return `{status: "ambiguous", candidates: [...]}` — UI shows a picker |

(Per locked decision: always confirm before creating a new person.)

### Step 4: Write

Assuming user confirms creation of Jerry Brown, colleague at Acme:

```
people:
  person_id: 01HXYZ...
  name: "Jerry Brown"
  name_lower: "jerry brown"
  company: "Acme"
  relationship_type: "colleague"
  tags: ["music-fan"]
  created_at: 2026-05-24T14:30:00Z
  updated_at: 2026-05-24T14:30:00Z

interactions:
  person_id: 01HXYZ...
  interaction_id: 01HXY1...
  date: 2026-05-24T14:25:00Z
  interaction_type: "casual"
  raw_input: "Water cooler with Jerry, he likes Fall Out Boy..."
  extracted_summary: "Brief hallway chat about music..."
  facts: [{"category": "interest", "content": "likes Fall Out Boy"}]
  tags_added: ["music-fan"]
  created_at: 2026-05-24T14:30:00Z

open_loops:
  person_id: 01HXYZ...
  loop_id: 01HXY2...
  description: "Jerry sending album link"
  due_date: 2026-05-29
  status: "open"
  source_interaction_id: 01HXY1...
  created_at: 2026-05-24T14:30:00Z
  updated_at: 2026-05-24T14:30:00Z
```

### Step 5: A Month Later — Brief

User asks: *"Brief me on Jerry, meeting Tuesday."*

The retrieval Lambda:
1. Resolves "Jerry" → `person_id` (same disambiguation logic as capture)
2. Queries all three tables by `person_id`
3. Hands the timeline + open loops to the AI provider with the **retrieval prompt** (separate from extraction — never combined)
4. Returns synthesized text:

> *"Jerry Brown, colleague at Acme. Music-fan. Last spoke at the water cooler in May — he likes Fall Out Boy and promised to send you the new album link (still open, was due May 29). Worth following up on as an opener."*

---

## ID Choice: Why ULID Over UUID

Both work. ULID has two practical wins:

1. **Sortable by creation time.** Listing interactions in time order is just `ORDER BY interaction_id`. With UUID you need a separate `created_at` index.
2. **More readable.** `01HXY1ABC...` is easier to eyeball in logs than `f47ac10b-58cc-4372-a567-0e02b2c3d479`.

ULIDs are 26 chars, URL-safe, monotonic within a millisecond. Standard library exists for every language.

## SQLite Schema (v1.0)

```sql
CREATE TABLE people (
    person_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    name_lower TEXT NOT NULL,
    company TEXT,
    relationship_type TEXT NOT NULL,
    tags TEXT,  -- JSON array
    pronunciation TEXT,
    nickname TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX idx_people_name_lower ON people(name_lower);

CREATE TABLE interactions (
    person_id TEXT NOT NULL,
    interaction_id TEXT NOT NULL,
    date TEXT NOT NULL,
    interaction_type TEXT NOT NULL,
    raw_input TEXT NOT NULL,
    raw_transcript TEXT,
    audio_blob_key TEXT,
    extracted_summary TEXT NOT NULL,
    facts TEXT,  -- JSON array
    tags_added TEXT,  -- JSON array
    created_at TEXT NOT NULL,
    PRIMARY KEY (person_id, interaction_id),
    FOREIGN KEY (person_id) REFERENCES people(person_id)
);

CREATE TABLE open_loops (
    person_id TEXT NOT NULL,
    loop_id TEXT NOT NULL,
    description TEXT NOT NULL,
    due_date TEXT,
    status TEXT NOT NULL,
    source_interaction_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    closed_at TEXT,
    PRIMARY KEY (person_id, loop_id),
    FOREIGN KEY (person_id) REFERENCES people(person_id)
);
CREATE INDEX idx_loops_status_due ON open_loops(status, due_date);

CREATE TABLE audit_log (
    audit_id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    source TEXT NOT NULL
);
```

## DynamoDB Schema (v1.1 — Planned)

```
Table: remi-people
  PK: person_id
  GSI: name-index (PK: name_lower)

Table: remi-interactions
  PK: person_id
  SK: interaction_id

Table: remi-open-loops
  PK: person_id
  SK: loop_id
  GSI: status-due-index (PK: status, SK: due_date)

Table: remi-audit-log
  PK: audit_id
  GSI: timestamp-index (PK: source, SK: timestamp)
```

Pricing model: on-demand for all tables. Personal scale = pennies/month. Point-in-time recovery enabled on all tables.

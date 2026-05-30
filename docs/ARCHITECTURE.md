# Architecture

REMI uses a **hexagonal (ports & adapters)** design. The core business logic
depends only on abstract interfaces. Concrete implementations — databases, AI
providers, file storage — plug in underneath and are the *only* place a vendor
SDK is allowed. This is locked Decision #1 (see [`DECISIONS.md`](../DECISIONS.md)).

Three diagrams:
1. [System architecture](#1-system-architecture) — the layers and adapters
2. [Capture data flow](#2-capture-data-flow) — what happens when you log an interaction
3. [Local deployment](#3-local-deployment) — the Docker topology

---

## 1. System architecture

Dependencies point **downward**. The core never reaches up into the API or out
to a provider SDK. Swap SQLite → DynamoDB or Anthropic → Ollama by changing
config, never core.

```mermaid
flowchart TD
    BROWSER["🖥️ Browser — HTMX + Tailwind + Jinja2<br/>Capture · People · Person · Brief · Settings"]
    API["⚙️ API Layer — FastAPI (api/main.py)<br/>routes: people · interactions · loops · briefs · reminders · models"]
    CORE["🧠 Core (core/) — no provider SDKs, ever<br/>models · provider-agnostic prompts · version"]
    CFG["config/settings.py<br/>reads env · builds + injects adapters"]

    BROWSER -->|HTTP| API --> CORE
    CFG -.injects.-> API

    CORE --> SP[Port: StorageProvider]
    CORE --> AP[Port: AIProvider]
    CORE --> BP[Port: BlobProvider]
    CORE --> TP[Port: TranscriptionProvider]

    SP --> SQLite([SQLite ●]) & Dynamo([DynamoDB ○])
    AP --> Anthropic([Anthropic ●]) & Ollama([Ollama ● + Manager]) & AIStub([OpenAI/Bedrock/Custom ○])
    BP --> FS([Filesystem ●]) & S3([S3 ○])
    TP --> Whisper([Whisper API ●]) & NoneT([None ●]) & WLocal([Whisper-local ○])

    Ollama -.HTTP.-> OllamaC[(ollama container)]
    Anthropic -.HTTPS.-> AnthAPI[(Anthropic API)]
```

**● = live in v1.0  ·  ○ = stubbed for v1.1** (raises `NotImplementedError`).

The four **ports** are abstract base classes in `adapters/*/base.py`. Each
concrete adapter implements one. `config/settings.py` is the only module that
reads environment variables — it builds the adapters and injects them into the
app at startup.

---

## 2. Capture data flow

Logging an interaction is a two-step flow: **extract → confirm**. Extraction is
read-only (nothing is saved until you confirm), so you always review what the AI
pulled out before it lands in your data.

```mermaid
sequenceDiagram
    actor User
    participant UI as Browser
    participant API as FastAPI
    participant TR as Transcription
    participant AI as AIProvider
    participant DB as Storage

    User->>UI: "Coffee with Jerry, he likes Fall Out Boy"
    UI->>API: POST /interactions/text (or /audio)
    opt audio input
        API->>TR: transcribe(audio)
        TR-->>API: text
    end
    API->>AI: extract_structured(prompt, text)
    AI-->>API: ExtractionResult<br/>(summary, facts, tags, loops, reminders)
    API->>DB: find_people_by_name("Jerry")
    DB-->>API: resolved · ambiguous · not found
    API-->>UI: extraction + person_resolution
    UI-->>User: show extracted card to review

    User->>UI: Confirm (pick or create person)
    UI->>API: POST /interactions/confirm
    API->>DB: create_interaction + open_loops + reminders
    API->>DB: write_audit_entry
    API-->>UI: 201 Saved
```

Recall (the brief) is the reverse: the API pulls a person's interactions, loops,
and reminders from storage and asks the `AIProvider` to synthesize a narrative
summary via `generate_text`.

---

## 3. Local deployment

`docker compose up` runs two containers on a private network. Only the app is
published to your machine; Ollama is internal-only. Data persists in three
bind-mounted volumes.

```mermaid
flowchart LR
    Browser["🖥️ Browser"]
    subgraph host["Your machine"]
        subgraph net["Docker network: remi-network"]
            App["remi-app<br/>FastAPI :8000"]
            Oll["ollama<br/>:11434 — internal only"]
        end
        V1[("./data<br/>SQLite DB")]
        V2[("./audio_storage<br/>audio blobs")]
        V3[("./ollama_data<br/>downloaded models")]
    end
    Cloud[("Hosted AI API<br/>Anthropic / OpenAI")]

    Browser -->|127.0.0.1:8000| App
    App -->|http://ollama:11434| Oll
    App --- V1
    App --- V2
    Oll --- V3
    App -. only if using a hosted provider .-> Cloud
```

**Privacy note:** with `AI_PROVIDER=ollama`, no interaction text leaves your
machine — extraction and briefs run entirely in the local Ollama container. The
hosted-AI arrow is dashed because it's only used when you configure a hosted
provider.

The cloud target (v1.1) keeps the same architecture: API Gateway + Lambda for
the API, DynamoDB for storage, S3 for blobs, CloudFront for the frontend. Those
adapters are stubbed today.

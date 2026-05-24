# Tests

## Strategy

- **Unit tests** for `core/` and `adapters/` — fast, no network
- **Integration tests** with real SQLite — verify end-to-end storage flows
- **Smoke tests** for the API — hit each endpoint with a known good payload
- **Mock AI providers** in tests — never burn real API tokens

## Structure (Planned)

```
tests/
├── unit/
│   ├── core/
│   │   └── test_models.py
│   └── adapters/
│       ├── storage/
│       │   └── test_sqlite.py
│       ├── ai/
│       │   ├── test_anthropic_api.py    (mocked)
│       │   └── test_ollama.py           (mocked)
│       └── blob/
│           └── test_filesystem.py
├── integration/
│   └── test_jerry_walkthrough.py        # The canonical end-to-end test
└── fixtures/
    └── audio_sample.webm                # Tiny test audio for transcription
```

## Run Tests

```bash
pip install -e ".[dev]"
pytest
```

## Coverage Targets

- `core/` — 95%+
- `adapters/storage/` — 90%+
- `adapters/ai/` — 80%+ (mocking limits realistic coverage)
- `api/` — 80%+
- Overall — 85%+

## The Jerry Test

`tests/integration/test_jerry_walkthrough.py` should implement the full
walkthrough from `DATA_MODEL.md`:

1. Submit "Water cooler with Jerry, he likes Fall Out Boy..."
2. Verify extraction returns expected ExtractionResult
3. Verify person resolution returns NEEDS_CLARIFICATION
4. Create Jerry explicitly
5. Submit interaction
6. Verify all three tables have the right data
7. Generate a brief
8. Verify brief text contains key facts and the open loop

Use mocked AI provider returning deterministic output. This test is the
canonical "does the whole thing work" check.

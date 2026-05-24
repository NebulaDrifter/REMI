# Frontend

**Status: Phase 8 of BUILD_PLAN.md — not yet implemented.**

## Plan

Simple static HTML/CSS/JS. No build pipeline, no React. Served by FastAPI in
local deployment, by S3 + CloudFront in cloud (v1.1).

**Stack:** HTMX + Tailwind + minimal vanilla JS (for the MediaRecorder API).

## Planned Screens

| Screen | Path | Purpose |
|---|---|---|
| **Capture** | `/` | Text input + audio recorder, primary daily-use screen |
| **People List** | `/people` | Searchable list of all contacts |
| **Person Detail** | `/people/{id}` | Interactions timeline, open loops, tags |
| **Brief** | `/people/{id}/brief` | Generated pre-meeting brief, copy-to-clipboard |
| **Settings** | `/settings` | View current provider config (read-only in v1) |

## Design Principles

- **Mobile-first.** Tyler will use this on his phone. One-column layouts.
- **Fast feedback on capture.** After submitting, immediately show extracted facts
  for confirmation. Don't make the user wait for a separate page.
- **Person disambiguation inline.** When extraction says "Jerry doesn't exist —
  add him?", that's an inline modal, not a redirect.
- **Keyboard-friendly.** All actions reachable without a mouse.
- **No animations except for state changes** (HTMX swap indicators).

## Security Notes

- CSP header set by FastAPI middleware
- All user-generated content (names, notes, transcripts) HTML-escaped
- CSRF token on state-changing requests
- No inline scripts — all JS in external files for stricter CSP

## File Structure (Planned)

```
frontend/
├── index.html              # Capture screen, served at /
├── templates/              # Server-rendered HTMX fragments
│   ├── person_list.html
│   ├── person_detail.html
│   ├── brief.html
│   └── settings.html
├── static/
│   ├── css/
│   │   └── tailwind.css    # Pre-built, no JS build pipeline
│   ├── js/
│   │   └── recorder.js     # MediaRecorder for voice memos
│   └── icons/
```

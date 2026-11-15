# SpaceScan

Onboard crew health monitoring for long-duration deep-space missions. Everything runs on the
cabin computer: the onboard server, the clinical database, the assisted analysis and the cockpit
interface work with no network connection.

## What it does

- Records vital signs, body composition, eye health, sleep, mood, cognition and heart/lung sounds.
- Compares every reading with clinical reference ranges and with each crew member's own
  pre-flight baseline, then raises advisories with step-by-step care.
- Shows crew-wide overviews and habit streaks on shared cabin displays.
- Includes a searchable medical guide that grows with physician-approved protocols.

## Layout

| Folder | Content |
| --- | --- |
| `backend/` | FastAPI onboard server, database schema and seed data, clinical services, tests |
| `frontend/` | Nuxt 4 cockpit interface (Vue 3, Tailwind CSS 4, ECharts), tests |

## Run locally

Backend (Python 3.12+):

```bash
cd backend
uv sync --extra dev
uv run python db/seed.py --reset    # creates and fills the database
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Frontend (Node 20+):

```bash
cd frontend
npm install
npm run dev                          # http://localhost:3000 (also reachable on the cabin network)
```

The assisted analysis uses a local language model server when one is available
(`SPACESCAN_LLM_MODEL` selects the model); without it the app falls back to rule-based guidance.

## Tests

```bash
cd backend && uv run pytest -q
cd frontend && npx vitest run
```

The frontend suite also checks project rules: palette tokens only, plain English on screen,
no external network calls and no restricted names.

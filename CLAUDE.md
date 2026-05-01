# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then fill in API keys

# Run development server
uvicorn main:app --reload
# API docs: http://localhost:8000/docs

# Run production
uvicorn main:app --host 0.0.0.0 --port $PORT
```

There are no test or lint commands configured.

## Architecture

This is a **VC founder sourcing tool** that automatically discovers early-stage stealth founders across multiple platforms and scores them 0–100 for VC deal flow.

### Data flow

1. **Scheduled crawlers** (`workers/`) run at fixed intervals and write raw signals to the `signals` table in SQLite
2. **Scoring engine** (`scoring.py`) re-aggregates all signals per founder into a score every 15 minutes
3. **FastAPI** (`main.py`) exposes the scored founders via REST; the scheduler and app share one SQLite connection pool opened at startup via `lifespan`

### Workers and their schedules

| Worker | File | Interval |
|---|---|---|
| Twitter keyword search | `twitter_crawler.py` | Every 30 min |
| LinkedIn Google dork | `google_dorker.py` | Every 6 hours |
| Proxycurl LinkedIn enricher | `proxycurl_enricher.py` | Every 2 hours |
| ProductHunt launches | `producthunt_crawler.py` | Daily 08:00 UTC |
| HackerNews talent | `hackernews_crawler.py` | Every 6 hours |
| Cross-platform profile link | `social_lookup.py` | Every 4 hours |

Workers are registered in `scheduler.py`. After 3 consecutive failures a job is auto-paused for 1 hour.

### Scoring weights (capped at 100)

LinkedIn stealth keyword +35 · ProductHunt launch +25 · Twitter stealth keyword +20 · Google dork +20 · GitHub new org +15 · investor connection +20 · multi-source bonus +15/+10 · Twitter followers 500–5k +10 · recent signal <7 days +10.

### Key API endpoints

- `GET /founders` — paginated, filterable list
- `GET /founders/{id}` — full profile with all signals
- `PATCH /founders/{id}` — update status/notes
- `POST /search/manual` — trigger on-demand Proxycurl enrichment
- `POST /workers/google-dorker/enable|disable|run-once` — runtime job control
- `GET /health` — scheduler + database status

### Environment variables

All config lives in `.env` (see `.env.example`). Key flags:
- `GOOGLE_DORKER_ENABLED` / `SOCIAL_LOOKUP_ENABLED` — toggle optional workers
- `MIN_SCORE_THRESHOLD` (default 40) — minimum score returned by the API
- `DATABASE_URL` — defaults to SQLite; set a `postgresql://` URL for production

Database runs in WAL mode for concurrent reads during scheduler + API access.

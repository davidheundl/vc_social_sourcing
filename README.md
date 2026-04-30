# VC Social Sourcing Tool

Automatically finds early-stage stealth founders across X/Twitter, LinkedIn, and ProductHunt — and scores them for VCs.

---

## How it works

The backend runs continuously on a server, crawling multiple sources for founder signals like `"stealth startup"`, `"just incorporated"`, or `"building in public"`. Every profile gets a score from 0–100 and is exposed via a REST API.

| Source | Method | Frequency |
|---|---|---|
| X / Twitter | Tweepy keyword search | Every 30 min |
| LinkedIn | Google Dorking + Proxycurl | Every 6 hours |
| ProductHunt | GraphQL API | Daily at 08:00 |

---

## Setup

```bash
git clone https://github.com/YOUR-USERNAME/vc-sourcing-tool.git
cd vc-sourcing-tool
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your API keys
uvicorn main:app --reload
```

Open `http://localhost:8000/docs` for the interactive API docs.

---

## Environment Variables

```
TWITTER_BEARER_TOKEN=
PROXYCURL_API_KEY=
SERPAPI_KEY=
PRODUCTHUNT_API_TOKEN=
```

---

## API Endpoints

```
GET  /founders          # List founders, filter by score/status
GET  /founders/{id}     # Full profile + signals
PATCH /founders/{id}    # Update status or notes
GET  /stats             # Totals and source breakdown
GET  /health            # Scheduler + worker status
POST /search/manual     # Enrich a LinkedIn URL on demand
```

---

## Deploy

Connect this repo to [Railway.app](https://railway.app), add your environment variables, and deploy. Live in ~2 minutes.

---

## Tech Stack

Python · FastAPI · APScheduler · SQLite · Tweepy · SerpAPI · Proxycurl

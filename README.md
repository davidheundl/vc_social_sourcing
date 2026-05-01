# VC Social Sourcing Tool

Automatically finds early-stage stealth founders across X/Twitter, LinkedIn, and ProductHunt — and scores them for VCs.

---

## How it works

The backend runs continuously on a server, crawling multiple sources for founder signals like `"stealth startup"`, `"just incorporated"`, or `"building in public"`. Every profile gets a score from 0–100 and is exposed via a REST API.

| Source | Method | Frequency |
|---|---|---|
| X / Twitter | Tweepy keyword search | Every 30 min |
| LinkedIn | Google Dorking via SerpAPI | Every 6 hours |
| LinkedIn | Proxycurl profile enrichment | Every 2 hours |
| ProductHunt | GraphQL API | Daily at 08:00 UTC |
| Scoring | Weighted signal aggregation | Every 15 min |

---

## Scoring Algorithm

| Signal | Points |
|---|---|
| LinkedIn stealth keyword | +35 |
| ProductHunt launch | +25 |
| Twitter stealth keyword | +20 |
| Google Dork result | +20 |
| GitHub new org | +15 |
| **Bonuses** | |
| 2+ sources confirming same person | +15 |
| 3+ sources | +10 more |
| Investor connection in DB | +20 |
| Twitter followers 500–5,000 | +10 |
| Signal within last 7 days | +10 |

Scores are capped at 100.

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/YOUR-USERNAME/vc-sourcing-tool.git
cd vc-sourcing-tool
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and add your API keys (see "Getting API Keys" below)
```

### 3. Run locally

```bash
uvicorn main:app --reload
```

Open `http://localhost:8000/docs` for the interactive Swagger UI.

---

## Getting API Keys

### Twitter / X Bearer Token
1. Go to [developer.twitter.com](https://developer.twitter.com/en/portal/dashboard)
2. Create a new Project and App
3. Enable **Read** permissions
4. Navigate to **Keys and Tokens** → copy the **Bearer Token**
5. Paste into `.env` as `TWITTER_BEARER_TOKEN`

> **Note:** The free tier (Essential Access) allows searching recent tweets. The Basic tier ($100/mo) gives higher rate limits — recommended for production.

### Proxycurl API Key
1. Sign up at [nubela.co/proxycurl](https://nubela.co/proxycurl)
2. Dashboard → **API Key** (top right)
3. Paste into `.env` as `PROXYCURL_API_KEY`

> Credits are consumed per enrichment call (~$0.01–$0.03 per profile). The tool handles 402 (out of credits) gracefully.

### SerpAPI Key
1. Sign up at [serpapi.com](https://serpapi.com)
2. Dashboard → your **API Key** is shown on the home screen
3. Paste into `.env` as `SERPAPI_KEY`

> The free tier includes 100 searches/month. Paid plans start at $50/mo.

### ProductHunt API Token
1. Go to [producthunt.com/v2/oauth/applications](https://www.producthunt.com/v2/oauth/applications)
2. Click **New Application**
3. Under **API Access**, generate a **Developer Token** (server-side)
4. Paste into `.env` as `PRODUCTHUNT_API_TOKEN`

> The Developer Token is rate-limited to 1,000 requests/day — more than enough for daily crawls.

---

## API Reference

### `GET /founders`

List founders sorted by score. Query params:

| Param | Default | Description |
|---|---|---|
| `min_score` | `40` | Filter by minimum score (0–100) |
| `status` | `null` | Filter: `new`, `reviewed`, `contacted`, `dismissed` |
| `limit` | `50` | Results per page (max 200) |
| `offset` | `0` | Pagination offset |

**Example response:**
```json
{
  "total": 142,
  "limit": 50,
  "offset": 0,
  "items": [
    {
      "id": 7,
      "name": "Jana Müller",
      "twitter_handle": "janabuilds",
      "linkedin_url": "https://linkedin.com/in/janamueller",
      "github_url": null,
      "score": 90,
      "signals": ["twitter", "linkedin", "producthunt"],
      "bio": "Building something stealth. Ex-Google. Seed-stage.",
      "location": "Berlin, Germany",
      "first_seen": "2025-04-28T14:22:01+00:00",
      "last_updated": "2025-04-29T08:10:44+00:00",
      "status": "new",
      "notes": ""
    }
  ]
}
```

---

### `GET /founders/{id}`

Full profile with all signals.

**Example response:**
```json
{
  "id": 7,
  "name": "Jana Müller",
  "score": 90,
  "signals": ["twitter", "linkedin", "producthunt"],
  "signal_records": [
    {
      "id": 23,
      "founder_id": 7,
      "source": "twitter",
      "signal_type": "twitter_stealth_keyword",
      "raw_text": "Day 1 of building in public. Can't share details yet but it's big.",
      "url": "https://twitter.com/i/web/status/1234567890",
      "created_at": "2025-04-28T14:22:01+00:00"
    }
  ]
}
```

---

### `PATCH /founders/{id}`

Update status or add notes.

**Request body:**
```json
{
  "status": "contacted",
  "notes": "Spoke with Jana on April 29 — interesting B2B SaaS angle in HR-tech."
}
```

---

### `GET /signals/recent`

Last N raw signals across all sources (default: 100).

**Example response:**
```json
[
  {
    "id": 99,
    "founder_id": 7,
    "source": "producthunt",
    "signal_type": "producthunt_launch",
    "raw_text": "Launched: HireAI — AI-powered HR automation (412 votes)",
    "url": "https://www.producthunt.com/posts/12345",
    "created_at": "2025-04-29T08:00:12+00:00"
  }
]
```

---

### `GET /stats`

Aggregate statistics.

**Example response:**
```json
{
  "total_founders": 142,
  "founders_today": 8,
  "average_score": 47.3,
  "by_source": {
    "twitter": 89,
    "linkedin": 34,
    "producthunt": 19,
    "google": 12
  }
}
```

---

### `POST /search/manual`

Trigger immediate Proxycurl enrichment for any LinkedIn URL.

**Request body:**
```json
{
  "linkedin_url": "https://linkedin.com/in/janamueller"
}
```

Returns the full enriched `FounderDetail` profile.

---

### `GET /health`

Scheduler and database status.

**Example response:**
```json
{
  "status": "running",
  "db_counts": {
    "founders": 142,
    "signals": 891,
    "investors": 10,
    "errors": 2
  },
  "jobs": [
    {
      "job_name": "twitter_crawler",
      "last_run": "2025-04-29T09:00:04+00:00",
      "last_count": 12,
      "consecutive_failures": 0,
      "paused_until": null
    }
  ]
}
```

---

## Deploy to Railway.app (5 steps)

1. **Push to GitHub** — commit all files and push to a public or private repo.

2. **Create a Railway project** — go to [railway.app](https://railway.app), click **New Project → Deploy from GitHub repo**, and select your repo.

3. **Add environment variables** — in the Railway dashboard, open your service → **Variables** → add all keys from `.env.example`.

4. **Set the start command** — Railway auto-detects Python apps. If needed, set the **Start Command** to:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

5. **Deploy** — Railway builds and deploys automatically. Your API is live at the generated `*.railway.app` URL within ~2 minutes.

> **Persistence:** Railway volumes are ephemeral by default. For SQLite persistence add a Railway **Volume** mounted at `/app` and set `DATABASE_URL=sqlite:////app/founders.db`. For production, switch to a Railway **PostgreSQL** plugin and update `DATABASE_URL` accordingly.

---

## Project Structure

```
vc-sourcing-tool/
├── main.py                    # FastAPI app + lifespan startup
├── scheduler.py               # APScheduler job definitions
├── database.py                # SQLite connection, schema, helpers
├── scoring.py                 # Weighted scoring algorithm
├── config.py                  # Environment variable loading
├── workers/
│   ├── __init__.py
│   ├── twitter_crawler.py     # Tweepy keyword search (every 30 min)
│   ├── google_dorker.py       # SerpAPI LinkedIn dorking (every 6 h)
│   ├── proxycurl_enricher.py  # Proxycurl profile enrichment (every 2 h)
│   └── producthunt_crawler.py # PH GraphQL maker crawler (daily 08:00)
├── models/
│   └── founder.py             # Pydantic request/response models
├── requirements.txt
├── .env.example
└── README.md
```

---

## Tech Stack

Python 3.11+ · FastAPI · APScheduler · SQLite (WAL mode) · Tweepy · SerpAPI · Proxycurl · ProductHunt GraphQL

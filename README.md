# X Talent Radar

Watches VC and angel investor accounts on X (Twitter) and detects who they newly follow — surfacing potential founders before they're well-known.

## How it works

1. **Fetch** — pulls the following lists of configured VC accounts via RapidAPI (twitter135)
2. **Diff** — compares against the last run and detects new follows
3. **Score** *(optional)* — runs each profile through a local LLM (Ollama) to score founder potential 0–10
4. **Display** — web UI to browse, filter, and search all profiles

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API key
```bash
cp .env.example .env
```
Edit `.env` and add your RapidAPI key:
```
RAPIDAPI_KEY=your_key_here
```
Get a key at [rapidapi.com](https://rapidapi.com) → search `twitter135` → subscribe.

### 3. Add VC accounts to watch
Edit `config.py` — add any X account by numeric ID.
Use [tweeterid.com](https://tweeterid.com) to look up IDs by username.

## Usage

```bash
# Run a scan (first run seeds the DB, second run shows new follows)
python main.py

# Show all detected signals
python main.py --signals

# Start the web UI
python app.py
# → http://localhost:8080
```

## AI Scoring (optional, free)

Uses a local Ollama model to score each profile's founder potential — no API key needed.

```bash
# One-time setup
brew install ollama
ollama pull llama3.2
ollama serve          # keep running in a separate terminal

# Score all profiles
python ai_filter.py
```

Scores:
- **8–10** — strong signal (engineer at top tech co, "building", "ex-FAANG")
- **5–7** — medium signal (tech background, investor-adjacent)
- **0–4** — weak/irrelevant

## Project structure

```
main.py          # CLI — run scans, show signals
app.py           # Flask web UI (localhost:8080)
watcher.py       # Core logic: fetch following lists, diff, save signals
ai_filter.py     # Optional: score profiles with local LLM
config.py        # VC accounts to watch, API provider configs
storage.py       # SQLite persistence
```

## Rate limits

| Plan | Requests/month | Scans/month (6 VCs) |
|---|---|---|
| Free | 500 | ~2 |
| Pro ($20) | 10,000 | ~33 (daily) |

## Stack

- [twitter135](https://rapidapi.com/omarmhaimdat/api/twitter135) via RapidAPI
- SQLite for state persistence
- Flask + vanilla HTML/CSS for the web UI
- Ollama (llama3.2) for local AI scoring

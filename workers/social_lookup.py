"""
Social Lookup — cross-platform enrichment for HackerNews and ProductHunt discoveries.

For founders identified via HN or PH who are missing a LinkedIn URL or Twitter handle,
this worker uses SerpAPI Google searches to locate their profiles on both platforms.
Newly found LinkedIn URLs are stored so the Proxycurl enricher can pick them up next run.

Runs every 4 hours via APScheduler.
Respects SOCIAL_LOOKUP_ENABLED flag (requires SerpAPI quota).
"""

import logging
import re
import time

import requests

from config import config
from database import get_db, upsert_founder, add_signal, log_job, log_error

logger = logging.getLogger("social_lookup")

SERPAPI_URL = "https://serpapi.com/search"

# How many founders to process per run — keeps SerpAPI spend predictable.
# Each founder costs up to 2 credits (1 LinkedIn search + 1 Twitter search).
MAX_PER_RUN = 25

LINKEDIN_URL_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w\-]+", re.IGNORECASE)
TWITTER_HANDLE_RE = re.compile(r"(?:twitter|x)\.com/([A-Za-z0-9_]{1,50})", re.IGNORECASE)

# Paths that are NOT personal profiles
_TWITTER_SKIP = {"search", "hashtag", "intent", "share", "home", "explore", "i"}


# ---------------------------------------------------------------------------
# SerpAPI helpers
# ---------------------------------------------------------------------------

def _serp_search(query: str) -> list[dict]:
    """Run one SerpAPI Google search; returns organic results list."""
    params = {
        "engine": "google",
        "q": query,
        "api_key": config.SERPAPI_KEY,
        "num": 5,
        "hl": "en",
        "gl": "us",
    }
    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=30)
        if resp.status_code == 429:
            logger.warning("SerpAPI rate limit — sleeping 60s")
            time.sleep(60)
            return []
        resp.raise_for_status()
        return resp.json().get("organic_results", [])
    except Exception as exc:
        logger.error("SerpAPI error: %s", exc)
        return []


def _find_linkedin_url(name: str) -> str | None:
    """Search Google for a person's LinkedIn profile by name."""
    query = f'site:linkedin.com/in "{name}"'
    results = _serp_search(query)
    for item in results:
        url = _extract_linkedin(item.get("link", "") + " " + item.get("snippet", ""))
        if url:
            return url
    return None


def _find_twitter_handle(name: str) -> str | None:
    """Search Google for a person's Twitter/X profile by name."""
    query = f'site:twitter.com OR site:x.com "{name}" -filter:retweets'
    results = _serp_search(query)
    for item in results:
        combined = item.get("link", "") + " " + item.get("snippet", "")
        handle = _extract_twitter_handle(combined)
        if handle:
            return handle
    return None


def _extract_linkedin(text: str) -> str | None:
    match = LINKEDIN_URL_RE.search(text)
    return match.group(0).rstrip("/") if match else None


def _extract_twitter_handle(text: str) -> str | None:
    for match in TWITTER_HANDLE_RE.finditer(text):
        handle = match.group(1)
        if handle.lower() not in _TWITTER_SKIP:
            return handle
    return None


# ---------------------------------------------------------------------------
# DB queries
# ---------------------------------------------------------------------------

def _founders_missing_linkedin(conn, limit: int) -> list[dict]:
    """
    Founders discovered via HN or ProductHunt who have no LinkedIn URL yet.
    Only considers founders with a non-null name (needed for the search query).
    """
    rows = conn.execute(
        """
        SELECT DISTINCT f.id, f.name, f.twitter_handle
        FROM founders f
        JOIN signals s ON s.founder_id = f.id
        WHERE s.source IN ('hackernews', 'producthunt')
          AND f.linkedin_url IS NULL
          AND f.name IS NOT NULL
          AND length(trim(f.name)) > 2
          AND NOT EXISTS (
              SELECT 1 FROM signals sx
              WHERE sx.founder_id = f.id
                AND sx.source = 'social_lookup'
                AND sx.signal_type = 'linkedin_search_attempted'
          )
        ORDER BY f.last_updated DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _founders_missing_twitter(conn, limit: int) -> list[dict]:
    """
    Founders from HackerNews with no Twitter handle yet.
    (ProductHunt already supplies twitterUsername, so they are excluded.)
    """
    rows = conn.execute(
        """
        SELECT DISTINCT f.id, f.name
        FROM founders f
        JOIN signals s ON s.founder_id = f.id
        WHERE s.source = 'hackernews'
          AND f.twitter_handle IS NULL
          AND f.name IS NOT NULL
          AND length(trim(f.name)) > 2
          AND NOT EXISTS (
              SELECT 1 FROM signals sx
              WHERE sx.founder_id = f.id
                AND sx.source = 'social_lookup'
                AND sx.signal_type = 'twitter_search_attempted'
          )
        ORDER BY f.last_updated DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def _mark_attempted(conn, founder_id: int, signal_type: str) -> None:
    """Record that we searched for this profile so we don't re-query on next run."""
    conn.execute(
        """INSERT INTO signals (founder_id, source, signal_type, raw_text, url, created_at)
           VALUES (?, 'social_lookup', ?, NULL, NULL, datetime('now'))""",
        (founder_id, signal_type),
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _lookup_linkedin(founder: dict) -> str | None:
    name: str = founder["name"]
    logger.info("Social Lookup: searching LinkedIn for '%s'", name)
    linkedin_url = _find_linkedin_url(name)

    with get_db() as conn:
        _mark_attempted(conn, founder["id"], "linkedin_search_attempted")

        if linkedin_url:
            # Update the founder record and add a signal
            conn.execute(
                "UPDATE founders SET linkedin_url = ?, last_updated = datetime('now') WHERE id = ?",
                (linkedin_url, founder["id"]),
            )
            add_signal(
                conn,
                founder_id=founder["id"],
                source="social_lookup",
                signal_type="linkedin_found",
                raw_text=f"LinkedIn found for '{name}'",
                url=linkedin_url,
            )
            logger.info("Social Lookup: LinkedIn found for '%s' → %s", name, linkedin_url)
        else:
            logger.info("Social Lookup: no LinkedIn found for '%s'", name)

    return linkedin_url


def _lookup_twitter(founder: dict) -> str | None:
    name: str = founder["name"]
    logger.info("Social Lookup: searching Twitter for '%s'", name)
    handle = _find_twitter_handle(name)

    with get_db() as conn:
        _mark_attempted(conn, founder["id"], "twitter_search_attempted")

        if handle:
            conn.execute(
                "UPDATE founders SET twitter_handle = ?, last_updated = datetime('now') WHERE id = ?",
                (handle, founder["id"]),
            )
            add_signal(
                conn,
                founder_id=founder["id"],
                source="social_lookup",
                signal_type="twitter_found",
                raw_text=f"Twitter found for '{name}'",
                url=f"https://twitter.com/{handle}",
            )
            logger.info("Social Lookup: Twitter found for '%s' → @%s", name, handle)
        else:
            logger.info("Social Lookup: no Twitter found for '%s'", name)

    return handle


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> int:
    if not config.SOCIAL_LOOKUP_ENABLED:
        logger.info("Social Lookup disabled (SOCIAL_LOOKUP_ENABLED=false) — skipping")
        with get_db() as conn:
            log_job(conn, "social_lookup", 0)
        return 0

    if not config.SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not set — skipping Social Lookup")
        with get_db() as conn:
            log_job(conn, "social_lookup", 0)
        return 0

    new_count = 0

    try:
        # --- LinkedIn lookups ---
        with get_db() as conn:
            linkedin_targets = _founders_missing_linkedin(conn, MAX_PER_RUN)

        for founder in linkedin_targets:
            linkedin_url = _lookup_linkedin(founder)
            if linkedin_url:
                new_count += 1
            time.sleep(2)  # polite delay between SerpAPI calls

        # --- Twitter lookups (HN founders only) ---
        with get_db() as conn:
            twitter_targets = _founders_missing_twitter(conn, MAX_PER_RUN)

        for founder in twitter_targets:
            handle = _lookup_twitter(founder)
            if handle:
                new_count += 1
            time.sleep(2)

        with get_db() as conn:
            log_job(conn, "social_lookup", new_count)

        logger.info(
            "Social Lookup finished — %d new profiles linked (LinkedIn + Twitter)", new_count
        )

    except Exception as exc:
        logger.error("Social Lookup fatal error: %s", exc)
        with get_db() as conn:
            log_error(conn, "social_lookup", str(exc))
            log_job(conn, "social_lookup", 0, failed=True)

    return new_count

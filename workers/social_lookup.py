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
from datetime import datetime, timezone

import requests
from sqlalchemy import exists
from sqlalchemy.orm import Session

from config import config
from app.services.worker_db import get_db, add_signal, log_job, log_error
from app.models.profile import Profile
from app.models.signal import Signal

logger = logging.getLogger("social_lookup")

SERPAPI_URL = "https://serpapi.com/search"

MAX_PER_RUN = 25

LINKEDIN_URL_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w\-]+", re.IGNORECASE)
TWITTER_HANDLE_RE = re.compile(r"(?:twitter|x)\.com/([A-Za-z0-9_]{1,50})", re.IGNORECASE)

_TWITTER_SKIP = {"search", "hashtag", "intent", "share", "home", "explore", "i"}


# ---------------------------------------------------------------------------
# SerpAPI helpers
# ---------------------------------------------------------------------------

def _serp_search(query: str) -> list[dict]:
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
    query = f'site:linkedin.com/in "{name}"'
    results = _serp_search(query)
    for item in results:
        url = _extract_linkedin(item.get("link", "") + " " + item.get("snippet", ""))
        if url:
            return url
    return None


def _find_twitter_handle(name: str) -> str | None:
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
# DB queries (SQLAlchemy)
# ---------------------------------------------------------------------------

def _profiles_missing_linkedin(db: Session, limit: int) -> list[dict]:
    already_attempted = (
        exists()
        .where(Signal.profile_id == Profile.id)
        .where(Signal.source == "social_lookup")
        .where(Signal.signal_type == "linkedin_search_attempted")
    )
    rows = (
        db.query(Profile.id, Profile.full_name, Profile.twitter_handle)
        .join(Signal, Signal.profile_id == Profile.id)
        .filter(
            Signal.source.in_(["hackernews", "producthunt"]),
            Profile.linkedin_url.is_(None),
            Profile.full_name.isnot(None),
            ~already_attempted,
        )
        .distinct()
        .order_by(Profile.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [{"id": r.id, "name": r.full_name, "twitter_handle": r.twitter_handle} for r in rows]


def _profiles_missing_twitter(db: Session, limit: int) -> list[dict]:
    already_attempted = (
        exists()
        .where(Signal.profile_id == Profile.id)
        .where(Signal.source == "social_lookup")
        .where(Signal.signal_type == "twitter_search_attempted")
    )
    rows = (
        db.query(Profile.id, Profile.full_name)
        .join(Signal, Signal.profile_id == Profile.id)
        .filter(
            Signal.source == "hackernews",
            Profile.twitter_handle.is_(None),
            Profile.full_name.isnot(None),
            ~already_attempted,
        )
        .distinct()
        .order_by(Profile.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [{"id": r.id, "name": r.full_name} for r in rows]


def _mark_attempted(db: Session, profile_id: int, signal_type: str) -> None:
    add_signal(db, profile_id=profile_id, source="social_lookup", signal_type=signal_type)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _lookup_linkedin(founder: dict) -> str | None:
    name: str = founder["name"]
    logger.info("Social Lookup: searching LinkedIn for '%s'", name)
    linkedin_url = _find_linkedin_url(name)

    with get_db() as db:
        _mark_attempted(db, founder["id"], "linkedin_search_attempted")

        if linkedin_url:
            profile = db.query(Profile).filter(Profile.id == founder["id"]).first()
            if profile:
                profile.linkedin_url = linkedin_url
                profile.updated_at = datetime.now(timezone.utc)
            add_signal(
                db,
                profile_id=founder["id"],
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

    with get_db() as db:
        _mark_attempted(db, founder["id"], "twitter_search_attempted")

        if handle:
            profile = db.query(Profile).filter(Profile.id == founder["id"]).first()
            if profile:
                profile.twitter_handle = handle
                profile.updated_at = datetime.now(timezone.utc)
            add_signal(
                db,
                profile_id=founder["id"],
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
        with get_db() as db:
            log_job(db, "social_lookup", 0)
        return 0

    if not config.SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not set — skipping Social Lookup")
        with get_db() as db:
            log_job(db, "social_lookup", 0)
        return 0

    new_count = 0

    try:
        with get_db() as db:
            linkedin_targets = _profiles_missing_linkedin(db, MAX_PER_RUN)

        for founder in linkedin_targets:
            linkedin_url = _lookup_linkedin(founder)
            if linkedin_url:
                new_count += 1
            time.sleep(2)

        with get_db() as db:
            twitter_targets = _profiles_missing_twitter(db, MAX_PER_RUN)

        for founder in twitter_targets:
            handle = _lookup_twitter(founder)
            if handle:
                new_count += 1
            time.sleep(2)

        with get_db() as db:
            log_job(db, "social_lookup", new_count)

        logger.info(
            "Social Lookup finished — %d new profiles linked (LinkedIn + Twitter)", new_count
        )

    except Exception as exc:
        logger.error("Social Lookup fatal error: %s", exc)
        with get_db() as db:
            log_error(db, "social_lookup", str(exc))
            log_job(db, "social_lookup", 0, failed=True)

    return new_count

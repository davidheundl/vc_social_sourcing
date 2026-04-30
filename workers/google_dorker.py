"""
Google Dorker — finds LinkedIn profiles of stealth founders via SerpAPI.
Runs every 6 hours via APScheduler.
"""

import logging
import re
import time

import requests

from config import config
from database import get_db, upsert_founder, add_signal, log_job, log_error

logger = logging.getLogger("google_dorker")

SERPAPI_URL = "https://serpapi.com/search"

DORK_QUERIES = [
    'site:linkedin.com/in "stealth startup" "founder"',
    'site:linkedin.com/in "stealth" "CEO" ("2024" OR "2025")',
    'site:linkedin.com/in "building something new" "founder"',
    'site:linkedin.com/in "working on something new" "founder"',
]

LINKEDIN_URL_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[\w\-]+")


def _extract_linkedin_url(text: str) -> str | None:
    match = LINKEDIN_URL_RE.search(text)
    return match.group(0).rstrip("/") if match else None


def _dork(query: str) -> list[dict]:
    """Execute one SerpAPI search and return result items."""
    params = {
        "engine": "google",
        "q": query,
        "api_key": config.SERPAPI_KEY,
        "num": 10,
        "hl": "en",
        "gl": "us",
    }
    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("organic_results", [])
    except requests.exceptions.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 429:
            logger.warning("SerpAPI rate limit — sleeping 60s")
            time.sleep(60)
        raise
    except Exception:
        raise


# ---------------------------------------------------------------------------
# Queued LinkedIn URLs for Proxycurl
# ---------------------------------------------------------------------------

_pending_linkedin_urls: list[str] = []


def get_pending_linkedin_urls() -> list[str]:
    """Called by proxycurl_enricher to get URLs discovered by this worker."""
    urls = list(_pending_linkedin_urls)
    _pending_linkedin_urls.clear()
    return urls


def run(force: bool = False) -> int:
    if not force and not config.GOOGLE_DORKER_ENABLED:
        logger.info("Google Dorker is disabled (GOOGLE_DORKER_ENABLED=false) — skipping")
        return 0
    if not config.SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not set — skipping Google Dorking")
        with get_db() as conn:
            log_job(conn, "google_dorker", 0)
        return 0

    new_count = 0
    seen_urls: set[str] = set()

    try:
        for query in DORK_QUERIES:
            logger.info("Google Dork: %s", query)
            try:
                results = _dork(query)
            except Exception as exc:
                logger.error("Google Dork query failed: %s", exc)
                with get_db() as conn:
                    log_error(conn, "google_dorker", str(exc))
                continue

            for item in results:
                link = item.get("link", "")
                title = item.get("title", "")
                snippet = item.get("snippet", "")

                linkedin_url = _extract_linkedin_url(link) or _extract_linkedin_url(snippet)
                if not linkedin_url:
                    continue
                if linkedin_url in seen_urls:
                    continue
                seen_urls.add(linkedin_url)

                # Best-effort name extraction from title (e.g. "Jane Doe - Founder at …")
                name: str | None = None
                if " - " in title:
                    name = title.split(" - ")[0].strip() or None

                with get_db() as conn:
                    fid = upsert_founder(
                        conn,
                        linkedin_url=linkedin_url,
                        name=name,
                    )
                    add_signal(
                        conn,
                        founder_id=fid,
                        source="google",
                        signal_type="google_dork_result",
                        raw_text=snippet,
                        url=linkedin_url,
                    )

                # Queue for Proxycurl enrichment
                _pending_linkedin_urls.append(linkedin_url)

                new_count += 1
                logger.info("Google Dork: found %s → %s", name or "unknown", linkedin_url)

            # Polite delay between queries
            time.sleep(2)

        with get_db() as conn:
            log_job(conn, "google_dorker", new_count)

        logger.info("Google Dorker finished — %d new LinkedIn profiles queued", new_count)

    except Exception as exc:
        logger.error("Google Dorker fatal error: %s", exc)
        with get_db() as conn:
            log_error(conn, "google_dorker", str(exc))
            log_job(conn, "google_dorker", 0, failed=True)

    return new_count

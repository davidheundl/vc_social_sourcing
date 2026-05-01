"""
HackerNews crawler — surfaces early-stage founder talent signals.
Uses the HN Algolia search API (no key required).
Runs every 6 hours via APScheduler.

Signal sources
--------------
1. "Show HN" posts  — founders demoing early products
2. "Ask HN: Who wants to be hired" monthly threads — people open to opportunities
3. Keyword searches for stealth/early-stage signals in HN stories/comments
"""

import logging
import re
import time

import requests

from app.services.worker_db import get_db, upsert_founder, add_signal, log_job, log_error

logger = logging.getLogger("hackernews_crawler")

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"

QUERY_SIGNAL_MAP: dict[str, str] = {
    "stealth startup founder": "hn_stealth_keyword",
    "building in stealth": "hn_stealth_keyword",
    "just incorporated": "hn_stealth_keyword",
    "pre-seed looking": "hn_stealth_keyword",
    "looking for cofounder": "hn_cofounder_search",
    "looking for co-founder": "hn_cofounder_search",
    "side project launch": "hn_launch",
    "soft launch": "hn_launch",
}

_GITHUB_RE = re.compile(r"github\.com/([A-Za-z0-9_-]+)", re.IGNORECASE)

_SESSION = requests.Session()
_SESSION.headers["User-Agent"] = "vc-social-sourcing/1.0"


def _get_json(url: str, params: dict | None = None, retries: int = 3) -> dict | list | None:
    for attempt in range(retries):
        try:
            resp = _SESSION.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 429:
                wait = 30 * (attempt + 1)
                logger.warning("HN API rate-limited — sleeping %ds", wait)
                time.sleep(wait)
            else:
                logger.error("HN HTTP error: %s", exc)
                return None
        except requests.exceptions.RequestException as exc:
            logger.warning("HN request failed (attempt %d): %s", attempt + 1, exc)
            time.sleep(5)
    return None


def _algolia_search(query: str, tags: str = "story", page: int = 0,
                    hits_per_page: int = 50) -> list[dict]:
    data = _get_json(HN_SEARCH_URL, params={
        "query": query,
        "tags": tags,
        "page": page,
        "hitsPerPage": hits_per_page,
    })
    if not data or "hits" not in data:
        return []
    return data["hits"]


def _process_show_hn(seen_usernames: set[str]) -> int:
    count = 0
    hits = _algolia_search("Show HN", tags="story", hits_per_page=100)

    for hit in hits:
        username = hit.get("author")
        if not username or username in seen_usernames:
            continue

        title: str = hit.get("title", "")
        hn_url = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"

        if not title.lower().startswith("show hn"):
            continue

        seen_usernames.add(username)

        with get_db() as db:
            fid = upsert_founder(db, name=username)
            add_signal(db, profile_id=fid, source="hackernews", signal_type="hn_show_hn",
                       raw_text=title, url=hn_url)
            count += 1
            logger.info("HN Show HN: saved founder '%s' — %s", username, title[:80])

    return count


def _process_who_wants_to_be_hired(seen_usernames: set[str]) -> int:
    count = 0
    hits = _algolia_search("Ask HN: Who wants to be hired", tags="story", hits_per_page=10)

    for thread in hits:
        thread_id = thread.get("objectID")
        if not thread_id:
            continue

        comments = _algolia_search("", tags=f"comment,story_{thread_id}", hits_per_page=100)

        for comment in comments:
            username = comment.get("author")
            if not username or username in seen_usernames:
                continue

            text: str = comment.get("comment_text") or ""
            if len(text) < 50:
                continue

            seen_usernames.add(username)

            github_match = _GITHUB_RE.search(text)
            github_url = f"https://github.com/{github_match.group(1)}" if github_match else None
            hn_url = f"https://news.ycombinator.com/item?id={comment.get('objectID')}"

            with get_db() as db:
                fid = upsert_founder(db, name=username, github_url=github_url)
                add_signal(db, profile_id=fid, source="hackernews",
                           signal_type="hn_who_wants_hired", raw_text=text[:500], url=hn_url)
                count += 1
                logger.info("HN hired thread: saved talent '%s'", username)

        break  # only process the most recent thread

    return count


def _process_keyword_searches(seen_usernames: set[str]) -> int:
    count = 0

    for query, signal_type in QUERY_SIGNAL_MAP.items():
        hits = _algolia_search(query, tags="story", hits_per_page=50)
        hits += _algolia_search(query, tags="comment", hits_per_page=50)

        for hit in hits:
            username = hit.get("author")
            if not username or username in seen_usernames:
                continue

            seen_usernames.add(username)

            title = hit.get("title") or hit.get("comment_text") or ""
            hn_url = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"

            with get_db() as db:
                fid = upsert_founder(db, name=username)
                add_signal(db, profile_id=fid, source="hackernews", signal_type=signal_type,
                           raw_text=title[:500], url=hn_url)
                count += 1
                logger.info("HN keyword '%s': saved founder '%s'", query, username)

        time.sleep(1)

    return count


def run() -> int:
    logger.info("HackerNews crawler starting")
    new_count = 0
    seen_usernames: set[str] = set()

    try:
        new_count += _process_show_hn(seen_usernames)
        new_count += _process_who_wants_to_be_hired(seen_usernames)
        new_count += _process_keyword_searches(seen_usernames)

        with get_db() as db:
            log_job(db, "hackernews_crawler", new_count)

        logger.info("HackerNews crawler finished — %d new signals", new_count)

    except Exception as exc:
        logger.error("HackerNews crawler fatal error: %s", exc)
        with get_db() as db:
            log_error(db, "hackernews_crawler", str(exc))
            log_job(db, "hackernews_crawler", 0, failed=True)

    return new_count

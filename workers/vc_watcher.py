"""
VC Watcher — two complementary signals from watched VC Twitter accounts:

1. Following scan  — detects when a VC starts following someone new
                     → stored as Signal(source="vc_watcher", signal_type="vc_new_follow")

2. Follower scan   — fetches the ~200 newest followers of each VC (1 page, reverse-chron)
                     → stored in vc_followers table for the multi-VC overlap query
                     → people who follow 3+ VCs within 48 h are high-intent founders

API usage: (1 following page + 1 follower page) × N accounts per scan.
With 8 accounts that's ~16 requests — well within RapidAPI Basic limits.
"""

import logging
import time
from datetime import datetime, timezone

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.vc_follower import VcFollower
from app.services.worker_db import get_db, upsert_founder, add_signal, log_job, log_error
from config import config

logger = logging.getLogger("vc_watcher")

# ---------------------------------------------------------------------------
# VC accounts to watch (numeric Twitter IDs)
# ---------------------------------------------------------------------------

WATCHED_ACCOUNTS = [
    {"name": "Paul Graham",         "id": "183749519",              "username": "paulg"},
    {"name": "Garry Tan",           "id": "11768582",               "username": "garrytan"},
    {"name": "Christoph Janz",      "id": "273383",                 "username": "chrija"},
    {"name": "Reshma Sohoni",       "id": "26743889",               "username": "reshmacs"},
    {"name": "Klaus Hommels",       "id": "21870345",               "username": "hommels"},
    {"name": "Balderton Capital",   "id": "16650886",               "username": "balderton"},
    {"name": "Atomico",             "id": "44579473",               "username": "atomico"},
    {"name": "NirkDowztski (test)", "id": "1467509644260225028",    "username": "NirkDowztski"},
]

WATCHER_NAMES = {w["id"]: w["name"] for w in WATCHED_ACCOUNTS}

# How many pages to fetch for the following list (200 users/page)
# Keep low to avoid long API calls — increases automatically over time via incremental scans
MAX_FOLLOWING_PAGES = 3
# Pages of followers per scan (each page ~50-70 users from the API)
MAX_FOLLOWER_PAGES = 5
# Multi-VC overlap thresholds
MIN_VC_OVERLAP = 3
FOLLOWER_WINDOW_HOURS = 48


# ---------------------------------------------------------------------------
# RapidAPI helpers
# ---------------------------------------------------------------------------

def _headers() -> dict:
    return {
        "x-rapidapi-key": config.RAPIDAPI_KEY,
        "x-rapidapi-host": "twitter135.p.rapidapi.com",
    }


def _parse_response(data: dict) -> tuple[list[dict], str | None]:
    """Parse twitter135 GraphQL following/followers response."""
    try:
        instructions = (
            data["data"]["user"]["result"]["timeline"]["timeline"]["instructions"]
        )
    except (KeyError, TypeError):
        return [], None

    entries = next((i["entries"] for i in instructions if "entries" in i), [])
    users, cursor_next = [], None

    for entry in entries:
        content = entry.get("content", {})
        item = content.get("itemContent", {})

        if item.get("itemType") == "TimelineUser":
            result = item.get("user_results", {}).get("result", {})
            legacy = result.get("legacy", {})
            uid = result.get("rest_id", "")
            if uid:
                users.append({
                    "id": uid,
                    "name": legacy.get("name", ""),
                    "username": legacy.get("screen_name", ""),
                    "description": legacy.get("description", ""),
                })

        if (
            content.get("entryType") == "TimelineTimelineCursor"
            and content.get("cursorType") == "Bottom"
        ):
            cursor_next = content.get("value")

    return users, cursor_next


def _fetch_pages(endpoint: str, watcher_id: str, max_pages: int) -> list[dict]:
    """Fetch up to max_pages pages from a following or followers endpoint."""
    results, cursor, pages = [], None, 0

    while pages < max_pages:
        params = {"id": watcher_id, "count": "200"}
        if cursor:
            params["cursor"] = cursor

        try:
            resp = requests.get(
                f"https://twitter135.p.rapidapi.com/v2/{endpoint}/",
                headers=_headers(),
                params=params,
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.error("Request error (%s, %s): %s", endpoint, watcher_id, exc)
            break

        if resp.status_code == 429:
            logger.warning("Rate limit — sleeping 60s")
            time.sleep(60)
            continue
        if resp.status_code != 200:
            logger.error("API error %d: %s", resp.status_code, resp.text[:200])
            break

        users, cursor = _parse_response(resp.json())
        if not users:
            break

        results.extend(users)
        pages += 1

        if not cursor or str(cursor) in ("0", "-1"):
            break

        time.sleep(1.5)

    return results


# ---------------------------------------------------------------------------
# Following scan — detects new follows, stores as Signals + Profile upsert
# ---------------------------------------------------------------------------

def _get_known_following(db: Session, watcher_id: str) -> set[str]:
    rows = db.execute(
        text("SELECT follower_id FROM vc_followers WHERE watcher_id = :wid"),
        {"wid": watcher_id},
    ).fetchall()
    # Reuse vc_followers to track known following state via a separate query on signals
    # Actually we track known following via Signal records
    sigs = db.execute(
        text(
            "SELECT raw_text FROM signals "
            "WHERE source = 'vc_watcher' AND signal_type = 'vc_known_following' "
            "AND url = :watcher_id"
        ),
        {"watcher_id": watcher_id},
    ).fetchall()
    return {r[0] for r in sigs}


def _save_known_following(db: Session, watcher_id: str, user_ids: list[str]) -> None:
    for uid in user_ids:
        db.execute(
            text(
                "INSERT INTO signals (source, signal_type, raw_text, url, created_at) "
                "VALUES ('vc_watcher', 'vc_known_following', :uid, :wid, :now) "
                "ON CONFLICT DO NOTHING"
            ),
            {"uid": uid, "wid": watcher_id, "now": datetime.now(timezone.utc)},
        )


def run_following_scan() -> int:
    """Detect new follows from each watched VC and store as talent signals."""
    if not config.RAPIDAPI_KEY:
        logger.warning("RAPIDAPI_KEY not set — skipping VC following scan")
        return 0

    new_count = 0

    for watcher in WATCHED_ACCOUNTS:
        watcher_id = watcher["id"]
        watcher_name = watcher["name"]
        logger.info("VC Following scan: checking %s", watcher_name)

        with get_db() as db:
            known = _get_known_following(db, watcher_id)

        current = _fetch_pages("Following", watcher_id, MAX_FOLLOWING_PAGES)
        if not current:
            logger.warning("VC Following scan: no data for %s", watcher_name)
            continue

        current_ids = [u["id"] for u in current]

        if not known:
            # First run — seed: save all followed accounts as profiles + mark as known
            with get_db() as db:
                for user in current:
                    profile_id = upsert_founder(
                        db,
                        twitter_handle=user["username"],
                        name=user["name"],
                        bio=user.get("description"),
                    )
                    add_signal(
                        db,
                        profile_id=profile_id,
                        source="vc_watcher",
                        signal_type="vc_following",
                        raw_text=f"{watcher_name} follows @{user['username']}",
                        url=f"https://x.com/{user['username']}",
                    )
                _save_known_following(db, watcher_id, current_ids)
            logger.info("VC Following scan: seeded %d profiles for %s", len(current_ids), watcher_name)
            new_count += len(current)
            continue

        new_follows = [u for u in current if u["id"] not in known]

        if new_follows:
            with get_db() as db:
                for user in new_follows:
                    profile_id = upsert_founder(
                        db,
                        twitter_handle=user["username"],
                        name=user["name"],
                        bio=user.get("description"),
                    )
                    add_signal(
                        db,
                        profile_id=profile_id,
                        source="vc_watcher",
                        signal_type="vc_new_follow",
                        raw_text=f"{watcher_name} started following @{user['username']}",
                        url=f"https://x.com/{user['username']}",
                    )
                    new_count += 1
                    logger.info(
                        "VC Following: %s → @%s", watcher_name, user["username"]
                    )
                _save_known_following(db, watcher_id, [u["id"] for u in new_follows])

        time.sleep(2)

    return new_count


# ---------------------------------------------------------------------------
# Follower scan — stores newest ~200 followers per VC for overlap detection
# ---------------------------------------------------------------------------

def run_follower_scan() -> int:
    """Fetch newest followers of each VC and store for multi-VC overlap detection."""
    if not config.RAPIDAPI_KEY:
        logger.warning("RAPIDAPI_KEY not set — skipping VC follower scan")
        return 0

    total = 0

    with SessionLocal() as db:
        for watcher in WATCHED_ACCOUNTS:
            users = _fetch_pages("Followers", watcher["id"], MAX_FOLLOWER_PAGES)
            if not users:
                logger.info("VC Followers: no data for %s", watcher["name"])
                continue

            for u in users:
                existing = db.get(VcFollower, (watcher["id"], u["id"]))
                if existing:
                    existing.username = u["username"]
                    existing.display_name = u["name"]
                    existing.description = u.get("description", "")
                else:
                    db.add(VcFollower(
                        watcher_id=watcher["id"],
                        follower_id=u["id"],
                        username=u["username"],
                        display_name=u["name"],
                        description=u.get("description", ""),
                    ))

            db.commit()
            total += len(users)
            logger.info("VC Followers: stored %d for %s", len(users), watcher["name"])
            time.sleep(1.5)

    return total


# ---------------------------------------------------------------------------
# Entry points for APScheduler
# ---------------------------------------------------------------------------

def run_following() -> int:
    try:
        count = run_following_scan()
        with get_db() as db:
            log_job(db, "vc_following_scan", count)
        return count
    except Exception as exc:
        logger.error("VC following scan failed: %s", exc)
        with get_db() as db:
            log_error(db, "vc_following_scan", str(exc))
            log_job(db, "vc_following_scan", 0, failed=True)
        return 0


def run_followers() -> int:
    try:
        count = run_follower_scan()
        with get_db() as db:
            log_job(db, "vc_follower_scan", count)
        return count
    except Exception as exc:
        logger.error("VC follower scan failed: %s", exc)
        with get_db() as db:
            log_error(db, "vc_follower_scan", str(exc))
            log_job(db, "vc_follower_scan", 0, failed=True)
        return 0

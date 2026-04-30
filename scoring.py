"""
Scoring algorithm for founder profiles.

Weights
-------
Signal type                               Points
-----------------------------------------  ------
linkedin_stealth_keyword                    +35
twitter_stealth_keyword                     +20
producthunt_launch                          +25
github_new_org                              +15
google_dork_result                          +20

Bonus multipliers (applied on top, then capped at 100)
-----------------------------------------  ------
2+ distinct sources confirming same person  +15
3+ distinct sources                         +10 additional
Investor connection in investor_db          +20
Twitter followers 500-5000                  +10
Signal within last 7 days                   +10
"""

import json
import logging
from datetime import datetime, timezone, timedelta

from database import get_db, utcnow

logger = logging.getLogger(__name__)

SIGNAL_WEIGHTS: dict[str, int] = {
    "linkedin_stealth_keyword": 35,
    "twitter_stealth_keyword": 20,
    "producthunt_launch": 25,
    "github_new_org": 15,
    "google_dork_result": 20,
}


def _has_recent_signal(signals: list[dict]) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    for sig in signals:
        created_at = sig.get("created_at", "")
        try:
            ts = datetime.fromisoformat(created_at)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                return True
        except (ValueError, TypeError):
            pass
    return False


def _has_investor_connection(conn, founder_id: int) -> bool:
    """
    Simple heuristic: check if any signal's raw_text mentions a known investor
    twitter handle or if the founder themselves appears in investor_db.
    """
    row = conn.execute(
        "SELECT twitter_handle, linkedin_url FROM founders WHERE id = ?", (founder_id,)
    ).fetchone()
    if not row:
        return False
    investors = conn.execute(
        "SELECT twitter_handle, linkedin_url FROM investor_db"
    ).fetchall()
    for inv in investors:
        if row["twitter_handle"] and inv["twitter_handle"]:
            if row["twitter_handle"].lower() == inv["twitter_handle"].lower():
                return True
        if row["linkedin_url"] and inv["linkedin_url"]:
            if row["linkedin_url"].lower() == inv["linkedin_url"].lower():
                return True
    return False


def score_founder(founder_id: int) -> int:
    with get_db() as conn:
        founder = conn.execute(
            "SELECT * FROM founders WHERE id = ?", (founder_id,)
        ).fetchone()
        if not founder:
            logger.warning("score_founder: founder %d not found", founder_id)
            return 0

        signals = conn.execute(
            "SELECT * FROM signals WHERE founder_id = ?", (founder_id,)
        ).fetchall()
        signal_dicts = [dict(s) for s in signals]

        score = 0

        # Base signal weights
        sources_hit: set[str] = set()
        for sig in signal_dicts:
            sig_type = sig.get("signal_type", "")
            source = sig.get("source", "")
            weight = SIGNAL_WEIGHTS.get(sig_type, 0)
            if weight:
                score += weight
                sources_hit.add(source)

        # Multi-source bonus
        if len(sources_hit) >= 2:
            score += 15
        if len(sources_hit) >= 3:
            score += 10

        # Investor connection bonus
        if _has_investor_connection(conn, founder_id):
            score += 20
            logger.debug("founder %d has investor connection (+20)", founder_id)

        # Twitter follower range bonus — stored in bio or a meta-signal raw_text
        follower_sig = conn.execute(
            """SELECT raw_text FROM signals
               WHERE founder_id = ? AND source = 'twitter' AND signal_type = 'follower_count'
               ORDER BY created_at DESC LIMIT 1""",
            (founder_id,),
        ).fetchone()
        if follower_sig:
            try:
                followers = int(follower_sig["raw_text"])
                if 500 <= followers <= 5000:
                    score += 10
            except (ValueError, TypeError):
                pass

        # Recent activity bonus
        if _has_recent_signal(signal_dicts):
            score += 10

        # Cap at 100
        score = min(score, 100)

        # Persist
        conn.execute(
            "UPDATE founders SET score = ?, last_updated = ? WHERE id = ?",
            (score, utcnow(), founder_id),
        )

        logger.debug("scored founder %d → %d (sources: %s)", founder_id, score, sources_hit)
        return score


def refresh_all_scores() -> int:
    """Re-score all founders whose signals were updated in the last 24 hours."""
    with get_db() as conn:
        rows = conn.execute(
            """SELECT DISTINCT founder_id FROM signals
               WHERE created_at >= datetime('now', '-1 day')"""
        ).fetchall()

    ids = [r["founder_id"] for r in rows]
    for fid in ids:
        try:
            score_founder(fid)
        except Exception as exc:
            logger.error("refresh_all_scores: failed for founder %d: %s", fid, exc)

    logger.info("refresh_all_scores: rescored %d founders", len(ids))
    return len(ids)

"""
Twitter/X crawler — searches for stealth founder signals using Tweepy.
Runs every 30 minutes via APScheduler.
"""

import logging
import time
from datetime import datetime, timezone

import tweepy

from config import config
from app.services.worker_db import get_db, upsert_founder, add_signal, log_job, log_error, is_investor

logger = logging.getLogger("twitter_crawler")

# Map query text → signal_type
QUERY_SIGNAL_MAP: dict[str, str] = {
    '"stealth startup"': "twitter_stealth_keyword",
    '"stealth mode founder"': "twitter_stealth_keyword",
    '"working on something stealth"': "twitter_stealth_keyword",
    '"building in public"': "twitter_stealth_keyword",
    '"day 1 of building"': "twitter_stealth_keyword",
    '"just quit my job to build"': "twitter_stealth_keyword",
    '"soft launch"': "twitter_stealth_keyword",
    '"just incorporated"': "twitter_stealth_keyword",
    '"just registered my company"': "twitter_stealth_keyword",
    '"looking for angel"': "twitter_stealth_keyword",
    '"pre-seed round"': "twitter_stealth_keyword",
    '"looking for cofounder"': "twitter_stealth_keyword",
}

BASE_FILTER = "-is:retweet (lang:en OR lang:de)"


def _build_client() -> tweepy.Client | None:
    if not config.RAPIDAPI_KEY:
        logger.warning("RAPIDAPI_KEY not set — skipping Twitter crawl")
        return None
    return tweepy.Client(
        bearer_token=config.RAPIDAPI_KEY,
        wait_on_rate_limit=False,
    )


def _search_with_backoff(client: tweepy.Client, query: str,
                         max_results: int = 100) -> list[dict]:
    """Search tweets, handling rate limits with exponential backoff."""
    attempts = 0
    backoff = 15  # seconds
    while attempts < 5:
        try:
            response = client.search_recent_tweets(
                query=query,
                max_results=max_results,
                tweet_fields=["author_id", "created_at", "text", "lang"],
                user_fields=["username", "name", "description", "public_metrics",
                             "location"],
                expansions=["author_id"],
            )
            if response.data is None:
                return []

            # Build user lookup
            users_by_id: dict[int, dict] = {}
            if response.includes and "users" in response.includes:
                for u in response.includes["users"]:
                    users_by_id[u.id] = {
                        "username": u.username,
                        "name": u.name,
                        "bio": u.description,
                        "followers": u.public_metrics.get("followers_count", 0)
                        if u.public_metrics else 0,
                        "location": getattr(u, "location", None),
                    }

            results = []
            for tweet in response.data:
                user = users_by_id.get(tweet.author_id, {})
                results.append({
                    "author_id": tweet.author_id,
                    "username": user.get("username"),
                    "name": user.get("name"),
                    "bio": user.get("bio"),
                    "followers": user.get("followers", 0),
                    "location": user.get("location"),
                    "tweet_text": tweet.text,
                    "tweet_url": f"https://twitter.com/i/web/status/{tweet.id}",
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                })
            return results

        except tweepy.errors.TooManyRequests:
            logger.warning(
                "Twitter rate limit hit — sleeping %ds (attempt %d)",
                backoff, attempts + 1
            )
            time.sleep(backoff)
            backoff = min(backoff * 2, 900)
            attempts += 1
        except tweepy.errors.TwitterServerError as exc:
            logger.error("Twitter server error: %s", exc)
            time.sleep(30)
            attempts += 1
        except Exception as exc:
            logger.error("Unexpected Twitter error: %s", exc)
            raise

    return []


def run() -> int:
    """Entry point called by APScheduler."""
    if not config.RAPIDAPI_KEY:
        logger.warning("Twitter crawler skipped: no RAPIDAPI_KEY configured")
        with get_db() as db:
            log_job(db, "twitter_crawler", 0)
        return 0

    client = _build_client()
    if client is None:
        return 0

    new_count = 0
    seen_author_ids: set[int] = set()

    queries = list(QUERY_SIGNAL_MAP.keys())

    try:
        for raw_query in queries:
            full_query = f"{raw_query} {BASE_FILTER} -followers:99"
            logger.info("Twitter: searching for %s", raw_query)

            try:
                tweets = _search_with_backoff(client, full_query, max_results=100)
            except Exception as exc:
                with get_db() as db:
                    log_error(db, "twitter_crawler", str(exc))
                logger.error("Twitter query failed (%s): %s", raw_query, exc)
                continue

            for entry in tweets:
                author_id = entry["author_id"]
                username = entry.get("username")
                followers = entry.get("followers", 0)

                if followers < 100:
                    continue
                if author_id in seen_author_ids:
                    continue
                seen_author_ids.add(author_id)

                with get_db() as db:
                    if is_investor(db, twitter_handle=username):
                        logger.info(
                            "Twitter: @%s is a known investor — skipping", username
                        )
                        continue

                    fid = upsert_founder(
                        db,
                        twitter_handle=username,
                        name=entry.get("name"),
                        bio=entry.get("bio"),
                        location=entry.get("location"),
                    )

                    signal_type = QUERY_SIGNAL_MAP.get(raw_query, "twitter_stealth_keyword")
                    add_signal(
                        db,
                        profile_id=fid,
                        source="twitter",
                        signal_type=signal_type,
                        raw_text=entry.get("tweet_text"),
                        url=entry.get("tweet_url"),
                    )

                    # Store follower count as meta-signal for scoring
                    add_signal(
                        db,
                        profile_id=fid,
                        source="twitter",
                        signal_type="follower_count",
                        raw_text=str(followers),
                    )

                    new_count += 1
                    logger.info(
                        "Twitter: saved founder @%s (followers=%d, query=%s)",
                        username, followers, raw_query,
                    )

        with get_db() as db:
            log_job(db, "twitter_crawler", new_count)

        logger.info("Twitter crawler finished — %d new signals", new_count)

    except Exception as exc:
        logger.error("Twitter crawler fatal error: %s", exc)
        with get_db() as db:
            log_error(db, "twitter_crawler", str(exc))
            log_job(db, "twitter_crawler", 0, failed=True)

    return new_count

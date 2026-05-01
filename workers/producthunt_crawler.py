"""
ProductHunt Crawler — finds recently launched products and their makers.
Runs once daily at 08:00 UTC via APScheduler.
"""

import logging
from datetime import datetime, timezone, timedelta

import requests

from config import config
from app.services.worker_db import get_db, upsert_founder, add_signal, log_job, log_error

logger = logging.getLogger("producthunt_crawler")

PH_GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"

POSTS_QUERY = """
query RecentPosts($after: String) {
  posts(first: 50, order: NEWEST, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        name
        tagline
        votesCount
        createdAt
        makers {
          id
          name
          username
          twitterUsername
          headline
          websiteUrl
          profileImage
        }
      }
    }
  }
}
"""


def _fetch_posts(after: str | None = None) -> dict:
    if not config.PRODUCTHUNT_API_TOKEN:
        raise RuntimeError("PRODUCTHUNT_API_TOKEN not set")

    headers = {
        "Authorization": f"Bearer {config.PRODUCTHUNT_API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    variables = {}
    if after:
        variables["after"] = after

    resp = requests.post(
        PH_GRAPHQL_URL,
        json={"query": POSTS_QUERY, "variables": variables},
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 429:
        logger.warning("ProductHunt rate limit hit — stopping pagination for this run")
        return None
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"ProductHunt GraphQL errors: {data['errors']}")
    return data.get("data", {}).get("posts", {})


def run() -> int:
    if not config.PRODUCTHUNT_API_TOKEN:
        logger.warning("PRODUCTHUNT_API_TOKEN not set — skipping ProductHunt crawl")
        with get_db() as db:
            log_job(db, "producthunt_crawler", 0)
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    new_count = 0
    cursor: str | None = None
    seen_maker_ids: set[str] = set()

    try:
        while True:
            try:
                page = _fetch_posts(after=cursor)
            except Exception as exc:
                logger.error("ProductHunt API error: %s", exc)
                with get_db() as db:
                    log_error(db, "producthunt_crawler", str(exc))
                break

            if page is None:
                break

            edges = page.get("edges", [])
            page_info = page.get("pageInfo", {})

            stop_paginating = False
            for edge in edges:
                post = edge.get("node", {})
                created_at_raw: str = post.get("createdAt", "")

                try:
                    post_dt = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
                    if post_dt < cutoff:
                        stop_paginating = True
                        break
                except (ValueError, TypeError):
                    pass

                product_name = post.get("name", "")
                tagline = post.get("tagline", "")
                votes = post.get("votesCount", 0)
                post_url = f"https://www.producthunt.com/posts/{post.get('id', '')}"

                for maker in post.get("makers", []):
                    maker_id = str(maker.get("id", ""))
                    if maker_id in seen_maker_ids:
                        continue
                    seen_maker_ids.add(maker_id)

                    twitter = maker.get("twitterUsername")
                    name = maker.get("name")
                    headline = maker.get("headline")

                    with get_db() as db:
                        fid = upsert_founder(db, twitter_handle=twitter, name=name, bio=headline)
                        add_signal(
                            db,
                            profile_id=fid,
                            source="producthunt",
                            signal_type="producthunt_launch",
                            raw_text=f"Launched: {product_name} — {tagline} ({votes} votes)",
                            url=post_url,
                        )

                    new_count += 1
                    logger.info(
                        "ProductHunt: maker %s launched '%s' (%d votes)",
                        name or maker.get("username"), product_name, votes,
                    )

            if stop_paginating or not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")

        with get_db() as db:
            log_job(db, "producthunt_crawler", new_count)

        logger.info("ProductHunt crawler finished — %d new maker signals", new_count)

    except Exception as exc:
        logger.error("ProductHunt crawler fatal error: %s", exc)
        with get_db() as db:
            log_error(db, "producthunt_crawler", str(exc))
            log_job(db, "producthunt_crawler", 0, failed=True)

    return new_count

"""
VC Signals router — exposes data from the VC Watcher workers.

GET /vc-signals/new-follows     — people a watched VC recently started following
GET /vc-signals/multi-vc        — people who followed 3+ VCs within 48h (high-intent founders)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import func, text

from app.database import SessionLocal
from app.models.signal import Signal
from app.models.vc_follower import VcFollower
from workers.vc_watcher import WATCHER_NAMES, MIN_VC_OVERLAP, FOLLOWER_WINDOW_HOURS

router = APIRouter(prefix="/vc-signals", tags=["VC Signals"])


@router.get("/new-follows")
def get_new_follows(limit: int = Query(default=50, ge=1, le=200)):
    """
    Returns people that watched VCs recently started following.
    Sorted by most recent signal first.
    """
    with SessionLocal() as db:
        rows = (
            db.query(Signal)
            .filter(
                Signal.source == "vc_watcher",
                Signal.signal_type == "vc_new_follow",
            )
            .order_by(Signal.created_at.desc())
            .limit(limit)
            .all()
        )

    return [
        {
            "profile_id": r.profile_id,
            "raw_text": r.raw_text,
            "url": r.url,
            "detected_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/multi-vc")
def get_multi_vc_followers(
    min_overlap: int = Query(default=MIN_VC_OVERLAP, ge=2, le=10),
    window_hours: int = Query(default=FOLLOWER_WINDOW_HOURS, ge=1, le=168),
):
    """
    Returns people who followed min_overlap or more watched VCs within the
    last window_hours hours — strong signal for founders seeking funding.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=window_hours)

    with SessionLocal() as db:
        rows = (
            db.query(
                VcFollower.follower_id,
                VcFollower.username,
                VcFollower.display_name,
                VcFollower.description,
                func.count(func.distinct(VcFollower.watcher_id)).label("vc_count"),
                func.group_concat(func.distinct(VcFollower.watcher_id)).label("watcher_ids"),
                func.min(VcFollower.first_seen).label("first_seen"),
            )
            .filter(VcFollower.first_seen >= since)
            .group_by(VcFollower.follower_id)
            .having(func.count(func.distinct(VcFollower.watcher_id)) >= min_overlap)
            .order_by(
                func.count(func.distinct(VcFollower.watcher_id)).desc(),
                func.min(VcFollower.first_seen).desc(),
            )
            .limit(200)
            .all()
        )

    return [
        {
            "follower_id": r.follower_id,
            "username": r.username,
            "display_name": r.display_name,
            "description": r.description,
            "vc_count": r.vc_count,
            "vcs_followed": [
                WATCHER_NAMES.get(wid.strip(), wid.strip())
                for wid in (r.watcher_ids or "").split(",")
                if wid.strip()
            ],
            "first_seen": r.first_seen.isoformat() if r.first_seen else None,
            "twitter_url": f"https://x.com/{r.username}" if r.username else None,
        }
        for r in rows
    ]

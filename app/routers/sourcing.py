"""
Sourcing endpoints: signals, stats, and worker controls.
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.job_log import ErrorLog, JobLog
from app.models.profile import Profile
from app.models.signal import Signal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Sourcing"])


@router.get("/signals/recent")
def recent_signals(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    signals = db.query(Signal).order_by(Signal.created_at.desc()).limit(limit).all()
    return [
        {
            "id": s.id,
            "profile_id": s.profile_id,
            "source": s.source,
            "signal_type": s.signal_type,
            "raw_text": s.raw_text,
            "url": s.url,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in signals
    ]


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Profile).count()
    today = datetime.now(timezone.utc).date()
    today_count = db.query(Profile).filter(func.date(Profile.created_at) == today).count()

    source_rows = (
        db.query(Signal.source, func.count(Signal.id).label("cnt"))
        .group_by(Signal.source)
        .all()
    )

    return {
        "total_profiles": total,
        "profiles_today": today_count,
        "by_source": {r.source: r.cnt for r in source_rows},
    }


@router.post("/workers/google-dorker/enable", tags=["Workers"])
def enable_google_dorker():
    from config import config
    config.GOOGLE_DORKER_ENABLED = True
    logger.warning("Google Dorker ENABLED via API — SerpAPI quota will be consumed")
    return {"google_dorker_enabled": True}


@router.post("/workers/google-dorker/disable", tags=["Workers"])
def disable_google_dorker():
    from config import config
    config.GOOGLE_DORKER_ENABLED = False
    logger.info("Google Dorker disabled via API")
    return {"google_dorker_enabled": False}


@router.post("/workers/google-dorker/run-once", tags=["Workers"])
async def run_google_dorker_once():
    from workers.google_dorker import run as dorker_run
    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(None, lambda: dorker_run(force=True))
    return {"new_signals": count}

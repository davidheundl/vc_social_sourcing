"""
SQLAlchemy helpers used by the scraper workers and scheduler.
Replaces the raw-SQLite database.py that came from the data-sourcing branch.
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.investor import InvestorProfile
from app.models.job_log import ErrorLog, JobLog
from app.models.profile import Profile
from app.models.signal import Signal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_SEED_INVESTORS = [
    ("Paul Graham",        "paulg",           "https://linkedin.com/in/paulgraham",     "angel",      ["b2b", "consumer", "infra"],              "San Francisco, CA"),
    ("Naval Ravikant",     "naval",            "https://linkedin.com/in/navalravikant",  "angel",      ["crypto", "saas", "consumer"],            "San Francisco, CA"),
    ("Alexis Ohanian",     "alexisohanian",    "https://linkedin.com/in/alexisohanian",  "vc",         ["consumer", "crypto", "social"],           "New York, NY"),
    ("Elad Gil",           "eladgil",          "https://linkedin.com/in/eladgil",        "angel",      ["b2b", "infra", "ai"],                    "San Francisco, CA"),
    ("Jason Calacanis",    "jason",            "https://linkedin.com/in/jasoncalacanis", "angel",      ["saas", "consumer", "fintech"],            "Los Angeles, CA"),
    ("Balaji Srinivasan",  "balajis",          "https://linkedin.com/in/balajis",        "angel",      ["crypto", "biotech", "ai"],               "San Francisco, CA"),
    ("Semil Shah",         "semil",            "https://linkedin.com/in/semilshah",      "micro_fund", ["b2b", "consumer", "marketplace"],         "San Francisco, CA"),
    ("Brianne Kimmel",     "briannekimmel",    "https://linkedin.com/in/briannekimmel",  "micro_fund", ["saas", "future_of_work"],                 "San Francisco, CA"),
    ("Harry Stebbings",    "hstebbings1996",   "https://linkedin.com/in/harrystebbings", "vc",         ["b2b", "saas", "fintech"],                 "London, UK"),
    ("Sahil Lavingia",     "shl",              "https://linkedin.com/in/sahillavingia",  "angel",      ["saas", "creator_economy"],               "Remote"),
]

_JOB_NAMES = [
    "twitter_crawler", "google_dorker", "proxycurl_enricher",
    "producthunt_crawler", "hackernews_crawler", "social_lookup",
    "scoring_refresh", "vc_following_scan", "vc_follower_scan",
]


def seed_investors(db: Session) -> None:
    if db.query(InvestorProfile).count() == 0:
        for name, handle, url, itype, focus, location in _SEED_INVESTORS:
            db.add(InvestorProfile(
                name=name, twitter_handle=handle, linkedin_url=url,
                investor_type=itype, focus_areas=focus, location=location,
            ))
        db.commit()
        logger.info("Seeded %d investors into investor_profiles", len(_SEED_INVESTORS))


def seed_job_logs(db: Session) -> None:
    for job_name in _JOB_NAMES:
        if not db.query(JobLog).filter(JobLog.job_name == job_name).first():
            db.add(JobLog(job_name=job_name))
    db.commit()

# ---------------------------------------------------------------------------
# Session context manager (drop-in for the old SQLite get_db())
# ---------------------------------------------------------------------------


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Helpers called by workers (mirror the old database.py API)
# ---------------------------------------------------------------------------


def upsert_founder(db: Session, *, twitter_handle: str | None = None,
                   linkedin_url: str | None = None, name: str | None = None,
                   bio: str | None = None, location: str | None = None,
                   github_url: str | None = None) -> int:
    """
    Upsert into the profiles table. linkedin_url is the primary dedup key;
    twitter_handle is the fallback. Returns the profile id.
    github_url is accepted for API compatibility but has no dedicated column.
    """
    profile = None
    if linkedin_url:
        profile = db.query(Profile).filter(Profile.linkedin_url == linkedin_url).first()
    if profile is None and twitter_handle:
        profile = db.query(Profile).filter(Profile.twitter_handle == twitter_handle).first()

    now = utcnow()

    if profile:
        if name and not profile.full_name:
            profile.full_name = name
        if bio and not profile.bio:
            profile.bio = bio
        if location and not profile.country:
            profile.country = location
        if linkedin_url and not profile.linkedin_url:
            profile.linkedin_url = linkedin_url
        if twitter_handle and not profile.twitter_handle:
            profile.twitter_handle = twitter_handle
        profile.updated_at = now
        db.flush()
        return profile.id

    profile = Profile(
        full_name=name or "Unknown",
        twitter_handle=twitter_handle,
        linkedin_url=linkedin_url,
        bio=bio,
        country=location,
        source="scraper",
        is_seed=False,
        twitter_followers=0,
        twitter_following=0,
        created_at=now,
        updated_at=now,
    )
    db.add(profile)
    db.flush()
    return profile.id


def add_signal(db: Session, *, profile_id: int, source: str, signal_type: str,
               raw_text: str | None = None, url: str | None = None) -> None:
    db.add(Signal(
        profile_id=profile_id,
        source=source,
        signal_type=signal_type,
        raw_text=raw_text,
        url=url,
        created_at=utcnow(),
    ))
    db.flush()


def log_job(db: Session, job_name: str, count: int, failed: bool = False) -> None:
    job = db.query(JobLog).filter(JobLog.job_name == job_name).first()
    if not job:
        job = JobLog(job_name=job_name)
        db.add(job)
    job.last_run = utcnow()
    if failed:
        job.consecutive_failures = (job.consecutive_failures or 0) + 1
    else:
        job.last_count = count
        job.consecutive_failures = 0
        job.paused_until = None
    db.flush()


def log_error(db: Session, source: str, message: str) -> None:
    db.add(ErrorLog(source=source, message=message, created_at=utcnow()))
    db.flush()


def is_investor(db: Session, twitter_handle: str | None = None,
                linkedin_url: str | None = None) -> bool:
    if twitter_handle and db.query(InvestorProfile).filter(
        InvestorProfile.twitter_handle == twitter_handle
    ).first():
        return True
    if linkedin_url and db.query(InvestorProfile).filter(
        InvestorProfile.linkedin_url == linkedin_url
    ).first():
        return True
    return False

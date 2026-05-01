"""
APScheduler setup. All workers are registered here.

Worker failure policy
---------------------
Each job is wrapped in _guarded(). If a job fails 3 consecutive times,
it is paused for 1 hour and a WARNING is printed to the console.
"""

import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.services.worker_db import get_db, log_job, log_error
from app.models.job_log import JobLog

logger = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None

MAX_CONSECUTIVE_FAILURES = 3
PAUSE_DURATION_HOURS = 1


def _is_paused(job_name: str) -> bool:
    with get_db() as db:
        job = db.query(JobLog).filter(JobLog.job_name == job_name).first()
        if job and job.paused_until:
            paused_until = job.paused_until
            if paused_until.tzinfo is None:
                paused_until = paused_until.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < paused_until:
                return True
            # Un-pause: reset consecutive_failures
            job.paused_until = None
            job.consecutive_failures = 0
    return False


def _check_and_maybe_pause(job_name: str) -> None:
    with get_db() as db:
        job = db.query(JobLog).filter(JobLog.job_name == job_name).first()
        if job and (job.consecutive_failures or 0) >= MAX_CONSECUTIVE_FAILURES:
            paused_until = datetime.now(timezone.utc) + timedelta(hours=PAUSE_DURATION_HOURS)
            job.paused_until = paused_until
            logger.warning(
                "Worker '%s' failed %d times in a row — pausing until %s",
                job_name, MAX_CONSECUTIVE_FAILURES, paused_until,
            )


def _guarded(job_name: str, func):
    """Wrap a worker function with failure counting and pause logic."""
    def wrapper():
        if _is_paused(job_name):
            logger.info("Worker '%s' is paused — skipping this run", job_name)
            return

        logger.info("[%s] Starting", job_name)
        start = datetime.now(timezone.utc)
        try:
            count = func()
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            logger.info(
                "[%s] Finished in %.1fs — %d new records", job_name, elapsed, count or 0
            )
        except Exception as exc:
            logger.error("[%s] Failed: %s", job_name, exc)
            with get_db() as db:
                log_error(db, job_name, str(exc))
                log_job(db, job_name, 0, failed=True)
            _check_and_maybe_pause(job_name)

    wrapper.__name__ = job_name
    return wrapper


def _scoring_refresh_job() -> int:
    from app.database import SessionLocal
    from app.models.profile import Profile
    from app.services.scoring_engine import compute_score

    count = 0
    with SessionLocal() as db:
        profiles = db.query(Profile).all()
        for profile in profiles:
            try:
                compute_score(profile, db)
                count += 1
            except Exception as exc:
                logger.error("scoring_refresh: failed for profile %d: %s", profile.id, exc)
    return count


def _twitter_job() -> int:
    from workers.twitter_crawler import run
    return run()


def _google_job() -> int:
    from workers.google_dorker import run
    return run()


def _proxycurl_job() -> int:
    from workers.proxycurl_enricher import run
    return run()


def _producthunt_job() -> int:
    from workers.producthunt_crawler import run
    return run()


def _hackernews_job() -> int:
    from workers.hackernews_crawler import run
    return run()


def _social_lookup_job() -> int:
    from workers.social_lookup import run
    return run()


def _vc_following_job() -> int:
    from workers.vc_watcher import run_following
    return run_following()


def _vc_follower_job() -> int:
    from workers.vc_watcher import run_followers
    return run_followers()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        _guarded("twitter_crawler", _twitter_job),
        trigger=IntervalTrigger(minutes=30),
        id="twitter_crawler",
        name="Twitter/X Stealth Crawler",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("google_dorker", _google_job),
        trigger=CronTrigger(hour="*/6"),
        id="google_dorker",
        name="Google Dorker (LinkedIn)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("proxycurl_enricher", _proxycurl_job),
        trigger=IntervalTrigger(hours=2),
        id="proxycurl_enricher",
        name="Proxycurl LinkedIn Enricher",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("producthunt_crawler", _producthunt_job),
        trigger=CronTrigger(hour=8, minute=0),
        id="producthunt_crawler",
        name="ProductHunt Maker Crawler",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("hackernews_crawler", _hackernews_job),
        trigger=CronTrigger(hour="*/6"),
        id="hackernews_crawler",
        name="HackerNews Talent Crawler",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("social_lookup", _social_lookup_job),
        trigger=CronTrigger(hour="2,6,10,14,18,22"),
        id="social_lookup",
        name="Social Profile Lookup (LinkedIn + Twitter)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("scoring_refresh", _scoring_refresh_job),
        trigger=IntervalTrigger(minutes=15),
        id="scoring_refresh",
        name="Founder Score Refresh",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("vc_following_scan", _vc_following_job),
        trigger=IntervalTrigger(minutes=5),
        id="vc_following_scan",
        name="VC Following Scanner",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("vc_follower_scan", _vc_follower_job),
        trigger=IntervalTrigger(minutes=5),
        id="vc_follower_scan",
        name="VC Follower Overlap Scanner",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info("APScheduler started with %d jobs", len(scheduler.get_jobs()))
    return scheduler


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler shut down")

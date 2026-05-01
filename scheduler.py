"""
APScheduler setup. All workers run once immediately on startup.
Scoring refresh continues every 15 minutes to update scores as data arrives.
"""

import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from database import get_db, log_job, log_error

logger = logging.getLogger("scheduler")

_scheduler: BackgroundScheduler | None = None

MAX_CONSECUTIVE_FAILURES = 3
PAUSE_DURATION_HOURS = 1


def _is_paused(job_name: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT paused_until FROM jobs_log WHERE job_name = ?", (job_name,)
        ).fetchone()
        if row and row["paused_until"]:
            paused_until = datetime.fromisoformat(row["paused_until"])
            if paused_until.tzinfo is None:
                paused_until = paused_until.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < paused_until:
                return True
            conn.execute(
                "UPDATE jobs_log SET paused_until = NULL, consecutive_failures = 0 WHERE job_name = ?",
                (job_name,),
            )
    return False


def _check_and_maybe_pause(job_name: str) -> None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT consecutive_failures FROM jobs_log WHERE job_name = ?", (job_name,)
        ).fetchone()
        if row and row["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
            paused_until = (
                datetime.now(timezone.utc) + timedelta(hours=PAUSE_DURATION_HOURS)
            ).isoformat()
            conn.execute(
                "UPDATE jobs_log SET paused_until = ? WHERE job_name = ?",
                (paused_until, job_name),
            )
            logger.warning(
                "Worker '%s' failed %d times in a row — pausing until %s",
                job_name, MAX_CONSECUTIVE_FAILURES, paused_until,
            )


def _guarded(job_name: str, func):
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
            with get_db() as conn:
                log_error(conn, job_name, str(exc))
                log_job(conn, job_name, 0, failed=True)
            _check_and_maybe_pause(job_name)

    wrapper.__name__ = job_name
    return wrapper


def _now(offset_seconds: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)


def _twitter_job() -> int:
    from workers.twitter_crawler import run
    return run()


def _google_job_forced() -> int:
    from workers.google_dorker import run
    return run(force=True)


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


def _scoring_refresh_job() -> int:
    from scoring import refresh_all_scores
    return refresh_all_scores()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler

    scheduler = BackgroundScheduler(timezone="UTC")

    # All crawlers run once immediately on startup, staggered by a few seconds
    # so they don't all hammer the DB at the exact same moment.
    scheduler.add_job(
        _guarded("twitter_crawler", _twitter_job),
        trigger=DateTrigger(run_date=_now(0)),
        id="twitter_crawler",
        name="Twitter/X Stealth Crawler (startup)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("producthunt_crawler", _producthunt_job),
        trigger=DateTrigger(run_date=_now(5)),
        id="producthunt_crawler",
        name="ProductHunt Maker Crawler (startup)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("google_dorker", _google_job_forced),
        trigger=DateTrigger(run_date=_now(10)),
        id="google_dorker",
        name="Google Dorker / SerpAPI (startup)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("hackernews_crawler", _hackernews_job),
        trigger=DateTrigger(run_date=_now(15)),
        id="hackernews_crawler",
        name="HackerNews Talent Crawler (startup)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("proxycurl_enricher", _proxycurl_job),
        trigger=DateTrigger(run_date=_now(20)),
        id="proxycurl_enricher",
        name="Proxycurl LinkedIn Enricher (startup)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        _guarded("social_lookup", _social_lookup_job),
        trigger=DateTrigger(run_date=_now(25)),
        id="social_lookup",
        name="Social Profile Lookup (startup)",
        replace_existing=True,
        max_instances=1,
    )

    # Scoring keeps refreshing every 15 min so scores update as data arrives
    scheduler.add_job(
        _guarded("scoring_refresh", _scoring_refresh_job),
        trigger=IntervalTrigger(minutes=15),
        id="scoring_refresh",
        name="Founder Score Refresh",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now(30),
    )

    scheduler.start()
    _scheduler = scheduler
    logger.info("APScheduler started — all crawlers will fire once on startup")
    return scheduler


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler shut down")

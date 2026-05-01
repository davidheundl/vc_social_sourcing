"""
Proxycurl Enricher — enriches LinkedIn profiles for founders in the DB.
Runs every 2 hours via APScheduler.
"""

import logging
from datetime import datetime, timezone

import requests
from sqlalchemy import exists

from config import config
from app.services.worker_db import get_db, upsert_founder, add_signal, log_job, log_error
from app.models.profile import Profile
from app.models.signal import Signal

logger = logging.getLogger("proxycurl_enricher")

PROXYCURL_PERSON_URL = "https://nubela.co/proxycurl/api/v2/linkedin"

STEALTH_KEYWORDS = {"stealth", "building", "new venture", "early stage", "pre-launch"}


def _is_stealth_profile(data: dict) -> bool:
    current_company: str = (data.get("current_company") or {}).get("name", "") or ""
    job_title: str = data.get("occupation", "") or ""
    summary: str = data.get("summary", "") or ""

    if "stealth" in current_company.lower():
        return True

    if "founder" in job_title.lower():
        experiences: list[dict] = data.get("experiences", []) or []
        for exp in experiences:
            company_name: str = (exp.get("company") or "").lower()
            if not company_name or "stealth" in company_name:
                return True
            starts_at: dict = exp.get("starts_at") or {}
            ends_at: dict | None = exp.get("ends_at")
            if ends_at is None and starts_at:
                start_year = starts_at.get("year", 0)
                if start_year >= datetime.now().year - 2:
                    return True

    summary_lower = summary.lower()
    for keyword in STEALTH_KEYWORDS:
        if keyword in summary_lower:
            return True

    return False


def _enrich_linkedin(linkedin_url: str) -> dict | None:
    headers = {"Authorization": f"Bearer {config.PROXYCURL_API_KEY}"}
    params = {"url": linkedin_url, "use_cache": "if-present"}

    try:
        resp = requests.get(PROXYCURL_PERSON_URL, headers=headers, params=params, timeout=30)

        if resp.status_code == 402:
            logger.warning("Proxycurl out of credits (402) — pausing enrichment")
            return None

        if resp.status_code == 404:
            logger.info("Proxycurl: LinkedIn profile not found: %s", linkedin_url)
            return {}

        resp.raise_for_status()
        return resp.json()

    except requests.exceptions.HTTPError as exc:
        logger.error("Proxycurl HTTP error for %s: %s", linkedin_url, exc)
        raise
    except Exception as exc:
        logger.error("Proxycurl error for %s: %s", linkedin_url, exc)
        raise


def enrich_url(linkedin_url: str) -> dict | None:
    """
    On-demand enrichment for a single LinkedIn URL.
    Returns a dict with basic profile info or None on failure.
    """
    if not config.PROXYCURL_API_KEY:
        logger.warning("PROXYCURL_API_KEY not set")
        return None

    try:
        data = _enrich_linkedin(linkedin_url)
    except Exception as exc:
        logger.error("enrich_url failed for %s: %s", linkedin_url, exc)
        return None

    if not data:
        return None

    _save_enriched(linkedin_url, data)

    with get_db() as db:
        profile = db.query(Profile).filter(Profile.linkedin_url == linkedin_url).first()
        return {"id": profile.id, "linkedin_url": profile.linkedin_url,
                "full_name": profile.full_name} if profile else None


def _save_enriched(linkedin_url: str, data: dict) -> None:
    full_name: str | None = data.get("full_name")
    location: str | None = data.get("city") or data.get("country_full_name")
    bio: str | None = data.get("summary")

    with get_db() as db:
        fid = upsert_founder(db, linkedin_url=linkedin_url, name=full_name, bio=bio, location=location)

        if _is_stealth_profile(data):
            add_signal(
                db,
                profile_id=fid,
                source="linkedin",
                signal_type="linkedin_stealth_keyword",
                raw_text=data.get("summary"),
                url=linkedin_url,
            )
            logger.info("Proxycurl: stealth signal detected for %s", full_name or linkedin_url)
        else:
            add_signal(
                db,
                profile_id=fid,
                source="linkedin",
                signal_type="linkedin_profile",
                raw_text=data.get("occupation"),
                url=linkedin_url,
            )

        profile = db.query(Profile).filter(Profile.id == fid).first()
        if profile:
            profile.updated_at = datetime.now(timezone.utc)


def run() -> int:
    if not config.PROXYCURL_API_KEY:
        logger.warning("PROXYCURL_API_KEY not set — skipping Proxycurl enrichment")
        with get_db() as db:
            log_job(db, "proxycurl_enricher", 0)
        return 0

    # Fetch profiles with linkedin_url that haven't had a linkedin signal yet
    already_enriched = exists().where(
        (Signal.profile_id == Profile.id) & (Signal.source == "linkedin")
    )
    with get_db() as db:
        rows = (
            db.query(Profile)
            .filter(Profile.linkedin_url.isnot(None), ~already_enriched)
            .limit(50)
            .all()
        )
        targets = [(r.id, r.linkedin_url) for r in rows]

    new_count = 0
    credits_exhausted = False

    for profile_id, linkedin_url in targets:
        if credits_exhausted:
            break

        logger.info("Proxycurl: enriching %s", linkedin_url)

        try:
            data = _enrich_linkedin(linkedin_url)
        except Exception as exc:
            with get_db() as db:
                log_error(db, "proxycurl_enricher", str(exc))
            continue

        if data is None:
            credits_exhausted = True
            break

        if not data:
            continue

        _save_enriched(linkedin_url, data)
        new_count += 1

    with get_db() as db:
        log_job(db, "proxycurl_enricher", new_count, failed=credits_exhausted)

    logger.info("Proxycurl enricher finished — %d profiles enriched", new_count)
    return new_count

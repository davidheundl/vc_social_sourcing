"""
Proxycurl Enricher — enriches LinkedIn profiles for founders in the DB.
Runs every 2 hours via APScheduler.
"""

import logging
from typing import Any

import requests

from config import config
from database import get_db, upsert_founder, add_signal, log_job, log_error, utcnow

logger = logging.getLogger("proxycurl_enricher")

PROXYCURL_PERSON_URL = "https://nubela.co/proxycurl/api/v2/linkedin"

STEALTH_KEYWORDS = {"stealth", "building", "new venture", "early stage", "pre-launch"}


def _is_stealth_profile(data: dict) -> bool:
    """Heuristic stealth detection from enriched Proxycurl data."""
    current_company: str = (data.get("current_company") or {}).get("name", "") or ""
    job_title: str = data.get("occupation", "") or ""
    summary: str = data.get("summary", "") or ""

    # current_company name contains "stealth"
    if "stealth" in current_company.lower():
        return True

    # job_title contains "founder" AND experience suggests unnamed/short-lived company
    if "founder" in job_title.lower():
        experiences: list[dict] = data.get("experiences", []) or []
        for exp in experiences:
            company_name: str = (exp.get("company") or "").lower()
            # Unnamed or explicitly "stealth" company
            if not company_name or "stealth" in company_name:
                return True
            # Short-lived: end_date is None means still active; check start year
            starts_at: dict = exp.get("starts_at") or {}
            ends_at: dict | None = exp.get("ends_at")
            if ends_at is None and starts_at:
                import datetime
                start_year = starts_at.get("year", 0)
                if start_year >= datetime.datetime.now().year - 2:
                    return True

    # Summary contains stealth signals
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
            return {}  # Empty dict signals "processed but no data"

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
    Public entry-point for on-demand enrichment (called from /search/manual endpoint).
    Returns the enriched founder dict or None on failure.
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

    # Return the founder row
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM founders WHERE linkedin_url = ?", (linkedin_url,)
        ).fetchone()
        return dict(row) if row else None


def _save_enriched(linkedin_url: str, data: dict) -> None:
    full_name: str | None = data.get("full_name")
    location: str | None = data.get("city") or data.get("country_full_name")
    bio: str | None = data.get("summary")

    with get_db() as conn:
        fid = upsert_founder(
            conn,
            linkedin_url=linkedin_url,
            name=full_name,
            bio=bio,
            location=location,
        )

        if _is_stealth_profile(data):
            add_signal(
                conn,
                founder_id=fid,
                source="linkedin",
                signal_type="linkedin_stealth_keyword",
                raw_text=data.get("summary"),
                url=linkedin_url,
            )
            logger.info("Proxycurl: stealth signal detected for %s", full_name or linkedin_url)
        else:
            # Still record that we processed this profile
            add_signal(
                conn,
                founder_id=fid,
                source="linkedin",
                signal_type="linkedin_profile",
                raw_text=data.get("occupation"),
                url=linkedin_url,
            )

        # Mark that this founder has been enriched via proxycurl
        conn.execute(
            "UPDATE founders SET last_updated = ? WHERE id = ?", (utcnow(), fid)
        )


def run() -> int:
    if not config.PROXYCURL_API_KEY:
        logger.warning("PROXYCURL_API_KEY not set — skipping Proxycurl enrichment")
        with get_db() as conn:
            log_job(conn, "proxycurl_enricher", 0)
        return 0

    # Fetch founders with a linkedin_url that have never had a linkedin signal
    with get_db() as conn:
        rows = conn.execute(
            """SELECT f.id, f.linkedin_url
               FROM founders f
               WHERE f.linkedin_url IS NOT NULL
                 AND NOT EXISTS (
                     SELECT 1 FROM signals s
                     WHERE s.founder_id = f.id AND s.source = 'linkedin'
                 )
               LIMIT 50"""
        ).fetchall()

    new_count = 0
    credits_exhausted = False

    for row in rows:
        if credits_exhausted:
            break

        linkedin_url = row["linkedin_url"]
        logger.info("Proxycurl: enriching %s", linkedin_url)

        try:
            data = _enrich_linkedin(linkedin_url)
        except Exception as exc:
            with get_db() as conn:
                log_error(conn, "proxycurl_enricher", str(exc))
            continue

        if data is None:
            # 402 = out of credits
            credits_exhausted = True
            break

        if not data:
            # 404 or empty
            continue

        _save_enriched(linkedin_url, data)
        new_count += 1

    with get_db() as conn:
        log_job(
            conn,
            "proxycurl_enricher",
            new_count,
            failed=credits_exhausted,
        )

    logger.info("Proxycurl enricher finished — %d profiles enriched", new_count)
    return new_count

"""
Ingestion helpers — convert raw scraped data (dict / list of dicts) into DB rows.

Expected input shape (flexible — missing fields are skipped):
{
  "external_id": "linkedin:johndoe",
  "full_name": "John Doe",
  "headline": "Founder at XYZ",
  "bio": "Building AI tools for...",
  "role": "Founder",
  "country": "France",
  "linkedin_url": "https://linkedin.com/in/johndoe",
  "twitter_handle": "johndoe",
  "twitter_followers": 1200,
  "company_name_raw": "XYZ",
  "source": "linkedin",
  "is_seed": false,
  "recent_posts": "...",
  "last_active_at": "2024-04-01T10:00:00"
}
"""
from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session

from app.models.profile import Profile


def upsert_profile(data: dict[str, Any], db: Session) -> Profile:
    external_id = data.get("external_id")
    existing = None
    if external_id:
        existing = db.query(Profile).filter(Profile.external_id == external_id).first()

    fields = [
        "full_name", "headline", "bio", "role", "country",
        "linkedin_url", "twitter_handle", "twitter_followers", "twitter_following",
        "company_name_raw", "source", "is_seed", "external_id", "recent_posts",
    ]

    if existing:
        for f in fields:
            if f in data:
                setattr(existing, f, data[f])
        if "last_active_at" in data and data["last_active_at"]:
            existing.last_active_at = _parse_dt(data["last_active_at"])
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    profile_data = {f: data.get(f) for f in fields}
    if data.get("last_active_at"):
        profile_data["last_active_at"] = _parse_dt(data["last_active_at"])
    profile_data.setdefault("full_name", "Unknown")
    profile_data.setdefault("twitter_followers", 0)
    profile_data.setdefault("twitter_following", 0)
    profile_data.setdefault("is_seed", False)

    profile = Profile(**profile_data)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def ingest_batch(records: list[dict[str, Any]], db: Session) -> list[Profile]:
    return [upsert_profile(r, db) for r in records]


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None

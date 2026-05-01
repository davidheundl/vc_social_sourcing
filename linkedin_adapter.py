"""
LinkedIn JSON → /ingest adapter.

Handles the most common LinkedIn API response formats:
  - Proxycurl  (full_name, occupation, summary, city, country_full_name, ...)
  - PhantomBuster (fullName, title, description, location, linkedInUrl, ...)
  - Apollo.io  (first_name + last_name, title, biography, country, linkedin_url, ...)
  - RapidAPI   (firstName + lastName, headline, location.city, profileUrl, ...)
  - Generic    (best-effort key matching)

Usage
-----
  from linkedin_adapter import normalize_profile, normalize_batch

  # Single record
  ingest_payload = normalize_profile(raw_linkedin_json)

  # Batch (list of records from your API)
  ingest_payload = normalize_batch(raw_list)

  # Then POST to /ingest/:
  import requests
  requests.post("http://localhost:8000/ingest/", json=ingest_payload)

CLI test
--------
  python linkedin_adapter.py sample_linkedin.json
"""

from __future__ import annotations

import json
import re
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

def _detect_format(record: dict) -> str:
    if "full_name" in record and "occupation" in record:
        return "proxycurl"
    if "fullName" in record and "linkedInUrl" in record:
        return "phantombuster"
    if "first_name" in record and "last_name" in record and "linkedin_url" in record:
        return "apollo"
    if "firstName" in record and "lastName" in record:
        return "rapidapi"
    return "generic"


# ---------------------------------------------------------------------------
# Per-format field extractors
# ---------------------------------------------------------------------------

def _from_proxycurl(r: dict) -> dict:
    twitter = r.get("twitter_handle") or ""
    if twitter.startswith("@"):
        twitter = twitter[1:]

    return {
        "full_name": r.get("full_name") or "",
        "role": r.get("occupation") or r.get("job_title") or "",
        "headline": r.get("headline") or "",
        "bio": r.get("summary") or "",
        "country": r.get("country_full_name") or r.get("country") or r.get("city") or "",
        "linkedin_url": r.get("linkedin_profile_url") or r.get("public_identifier") or "",
        "twitter_handle": twitter,
        "twitter_followers": _int(r.get("follower_count")),
        "company_name_raw": _current_company_name(r),
        "external_id": r.get("public_identifier") or "",
        "source": "proxycurl",
    }


def _from_phantombuster(r: dict) -> dict:
    twitter = r.get("twitterUrl") or ""
    handle = _extract_twitter_handle(twitter)
    linkedin = r.get("linkedInUrl") or r.get("profileUrl") or ""

    return {
        "full_name": r.get("fullName") or "",
        "role": r.get("title") or "",
        "headline": r.get("title") or "",
        "bio": r.get("description") or r.get("summary") or "",
        "country": _location_to_country(r.get("location") or ""),
        "linkedin_url": linkedin,
        "twitter_handle": handle,
        "twitter_followers": _int(r.get("followersCount")),
        "company_name_raw": r.get("companyName") or "",
        "external_id": _slug_from_url(linkedin),
        "source": "phantombuster",
    }


def _from_apollo(r: dict) -> dict:
    first = r.get("first_name") or ""
    last = r.get("last_name") or ""
    full = r.get("name") or f"{first} {last}".strip()
    twitter = r.get("twitter_url") or ""
    handle = _extract_twitter_handle(twitter)

    return {
        "full_name": full,
        "role": r.get("title") or "",
        "headline": r.get("headline") or r.get("title") or "",
        "bio": r.get("biography") or r.get("bio") or "",
        "country": r.get("country") or r.get("location") or "",
        "linkedin_url": r.get("linkedin_url") or "",
        "twitter_handle": handle,
        "twitter_followers": _int(r.get("twitter_followers")),
        "company_name_raw": r.get("organization_name") or r.get("company") or "",
        "external_id": _slug_from_url(r.get("linkedin_url") or ""),
        "source": "apollo",
    }


def _from_rapidapi(r: dict) -> dict:
    first = r.get("firstName") or ""
    last = r.get("lastName") or ""
    full = r.get("fullName") or f"{first} {last}".strip()
    location = r.get("location") or {}
    country = ""
    if isinstance(location, dict):
        country = location.get("country") or location.get("countryCode") or location.get("city") or ""
    elif isinstance(location, str):
        country = _location_to_country(location)

    linkedin = r.get("profileUrl") or r.get("linkedInUrl") or ""
    twitter = r.get("twitterHandle") or r.get("twitter") or ""
    if twitter.startswith("@"):
        twitter = twitter[1:]

    return {
        "full_name": full,
        "role": r.get("headline") or "",
        "headline": r.get("headline") or "",
        "bio": r.get("summary") or r.get("about") or "",
        "country": country,
        "linkedin_url": linkedin,
        "twitter_handle": twitter,
        "twitter_followers": _int(r.get("followersCount") or r.get("followers")),
        "company_name_raw": _nested_str(r, "currentPosition", "companyName")
                            or _nested_str(r, "company", "name") or "",
        "external_id": _slug_from_url(linkedin),
        "source": "rapidapi",
    }


def _from_generic(r: dict) -> dict:
    """Best-effort mapping for unknown formats."""
    full_name = (
        r.get("full_name") or r.get("fullName") or r.get("name") or
        f"{r.get('first_name','') or r.get('firstName','')} {r.get('last_name','') or r.get('lastName','')}".strip()
    )
    linkedin = (
        r.get("linkedin_url") or r.get("linkedInUrl") or r.get("profileUrl") or
        r.get("linkedin") or ""
    )
    twitter_raw = (
        r.get("twitter_handle") or r.get("twitterUrl") or r.get("twitter") or ""
    )
    bio = (
        r.get("bio") or r.get("summary") or r.get("description") or
        r.get("about") or r.get("biography") or ""
    )
    location = (
        r.get("country") or r.get("location") or r.get("city") or
        r.get("country_full_name") or ""
    )

    return {
        "full_name": full_name,
        "role": r.get("role") or r.get("title") or r.get("occupation") or r.get("headline") or "",
        "headline": r.get("headline") or r.get("title") or "",
        "bio": bio if isinstance(bio, str) else "",
        "country": _location_to_country(location) if isinstance(location, str) else "",
        "linkedin_url": linkedin,
        "twitter_handle": _extract_twitter_handle(twitter_raw),
        "twitter_followers": _int(r.get("twitter_followers") or r.get("followersCount")),
        "company_name_raw": (
            r.get("company_name_raw") or r.get("companyName") or
            r.get("organization_name") or r.get("company") or ""
        ),
        "external_id": _slug_from_url(linkedin),
        "source": "linkedin",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_profile(raw: dict) -> dict:
    """
    Normalize a single LinkedIn API record into the /ingest payload format.
    Returns a dict matching ProfileCreate schema.
    """
    fmt = _detect_format(raw)
    extractors = {
        "proxycurl": _from_proxycurl,
        "phantombuster": _from_phantombuster,
        "apollo": _from_apollo,
        "rapidapi": _from_rapidapi,
        "generic": _from_generic,
    }
    normalized = extractors[fmt](raw)

    # Sanitize: strip empty strings, enforce full_name fallback
    normalized = {k: (v if v != "" else None) for k, v in normalized.items()}
    normalized["full_name"] = normalized.get("full_name") or "Unknown"
    normalized["twitter_followers"] = normalized.get("twitter_followers") or 0
    normalized["twitter_following"] = 0
    normalized["is_seed"] = False

    return normalized


def normalize_batch(records: list[dict]) -> list[dict]:
    """Normalize a list of LinkedIn API records. Skips records with no full_name."""
    result = []
    for i, r in enumerate(records):
        try:
            normalized = normalize_profile(r)
            if normalized["full_name"] != "Unknown" or normalized.get("linkedin_url"):
                result.append(normalized)
        except Exception as exc:
            print(f"  [adapter] skipped record {i}: {exc}")
    return result


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _int(val: Any) -> int:
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0


def _extract_twitter_handle(url_or_handle: str) -> str | None:
    if not url_or_handle:
        return None
    match = re.search(r"(?:twitter|x)\.com/([A-Za-z0-9_]{1,50})", url_or_handle)
    if match:
        handle = match.group(1)
        return handle if handle.lower() not in {"search", "home", "intent", "share"} else None
    handle = url_or_handle.lstrip("@").strip()
    return handle or None


def _slug_from_url(url: str) -> str | None:
    match = re.search(r"linkedin\.com/in/([A-Za-z0-9\-_%]+)", url)
    return match.group(1) if match else None


def _location_to_country(location: str) -> str:
    """Extract the country portion from a 'City, Country' location string."""
    if not location:
        return ""
    parts = [p.strip() for p in location.split(",")]
    return parts[-1] if len(parts) > 1 else parts[0]


def _current_company_name(proxycurl_record: dict) -> str:
    """Extract company name from Proxycurl's nested structure."""
    experiences = proxycurl_record.get("experiences") or []
    for exp in experiences:
        if exp.get("ends_at") is None and exp.get("company"):
            return exp["company"]
    current = proxycurl_record.get("current_company") or {}
    return current.get("name") or ""


def _nested_str(d: dict, *keys: str) -> str:
    for key in keys:
        d = d.get(key) or {}
        if isinstance(d, str):
            return d
    return ""


# ---------------------------------------------------------------------------
# CLI test mode
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python linkedin_adapter.py <input.json> [--post http://localhost:8000]")
        print("\nExample input (PhantomBuster format):")
        sample = [
            {
                "fullName": "Jane Smith",
                "title": "Founder & CEO at Stealth AI",
                "description": "Building an AI tool. MVP live, raising pre-seed round.",
                "location": "Paris, France",
                "linkedInUrl": "https://linkedin.com/in/janesmith",
                "twitterUrl": "https://twitter.com/janesmith_ai",
                "companyName": "Stealth AI",
            }
        ]
        print(json.dumps(sample, indent=2))
        sys.exit(0)

    with open(sys.argv[1]) as f:
        raw = json.load(f)

    records = raw if isinstance(raw, list) else [raw]
    normalized = normalize_batch(records)

    print(f"Detected {len(records)} record(s), normalized {len(normalized)}:\n")
    print(json.dumps(normalized, indent=2, default=str))

    # Optionally POST to /ingest
    if "--post" in sys.argv:
        idx = sys.argv.index("--post")
        base_url = sys.argv[idx + 1]
        import urllib.request
        data = json.dumps(normalized).encode()
        req = urllib.request.Request(
            f"{base_url}/ingest/",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
            print(f"\nIngested: {len(result)} profiles → {base_url}/ingest/")

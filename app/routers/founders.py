"""
Founders router — returns only relevant scored profiles for the React frontend.

Relevant = a VC recently started following them, OR they follow one or more watched VCs.

GET /founders      — relevant scored profiles as Founder objects
GET /founders/vcs  — the 8 watched VC nodes
"""

import re
from typing import List

from fastapi import APIRouter
from sqlalchemy import func

from app.database import SessionLocal
from app.models.profile import Profile
from app.models.scoring import Score
from app.models.signal import Signal
from app.models.vc_follower import VcFollower

router = APIRouter(prefix="/founders", tags=["Founders"])

# ---------------------------------------------------------------------------
# Sector inference
# ---------------------------------------------------------------------------
SECTOR_KEYWORDS = [
    ("AI / ML", ["ai", "ml", "machine learning", "llm", "gpt", "neural", "deep learning", "artificial intelligence"]),
    ("Fintech", ["fintech", "finance", "banking", "payments", "crypto", "blockchain", "defi", "neobank"]),
    ("Developer Tools", ["developer", "devtools", "api", "sdk", "infrastructure", "platform", "open source", "github"]),
    ("Climate", ["climate", "sustainability", "carbon", "green", "energy", "solar", "cleantech"]),
    ("B2B SaaS", ["saas", "b2b", "enterprise", "workflow", "automation"]),
    ("Consumer", ["consumer", "marketplace", "social", "app", "mobile"]),
]

def infer_sector(bio: str | None) -> str:
    if not bio:
        return "Other"
    text = bio.lower()
    for sector, keywords in SECTOR_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return sector
    return "Other"

def activity_from_score(score: float) -> str:
    if score >= 45:
        return "hot"
    if score >= 20:
        return "warm"
    return "cold"

def extract_vc_name(raw_text: str | None) -> str:
    if not raw_text:
        return "Unknown VC"
    for pattern in [r"^(.+?)\s+started following\s+@", r"^(.+?)\s+follows\s+@"]:
        m = re.match(pattern, raw_text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return raw_text[:50]


# ---------------------------------------------------------------------------
# VC nodes endpoint — our 8 watched accounts
# ---------------------------------------------------------------------------

@router.get("/vcs")
def list_vc_nodes():
    """Return the watched VC accounts as VCNode objects for the graph."""
    from workers.vc_watcher import WATCHED_ACCOUNTS
    return [
        {
            "id": f"vc-{w['id']}",
            "name": w["name"],
            "type": "vc",
            "logo": f"https://unavatar.io/twitter/{w['username']}",
            "employee": w["name"],
            "employeeRole": "@" + w["username"],
            "subscribedAt": "2026-01-01",
        }
        for w in WATCHED_ACCOUNTS
    ]


# ---------------------------------------------------------------------------
# Main founders endpoint — only relevant profiles
# ---------------------------------------------------------------------------

@router.get("")
def list_founders():
    """
    Returns only high-signal profiles:
    - People who follow 2+ watched VCs (multi-VC followers), OR
    - A watched VC recently started following them (vc_new_follow signal)

    Only profiles with score > 0 are included.
    """
    from workers.vc_watcher import WATCHER_NAMES

    with SessionLocal() as db:
        # Handles of people who follow 2+ distinct watched VCs
        multi_vc_handles = {
            r[0].lower() for r in db.query(VcFollower.username)
            .group_by(VcFollower.username)
            .having(func.count(func.distinct(VcFollower.watcher_id)) >= 2)
            .all()
            if r[0]
        }

        # Profile IDs that a VC newly started following
        new_follow_ids = {
            r[0] for r in db.query(Signal.profile_id)
            .filter(
                Signal.source == "vc_watcher",
                Signal.signal_type == "vc_new_follow",
            )
            .distinct()
            .all()
        }

        # Load scored profiles with score > 0
        rows = (
            db.query(Profile, Score)
            .join(Score, Score.profile_id == Profile.id)
            .filter(Score.total > 0)
            .order_by(Score.total.desc())
            .all()
        )

        result = []
        for profile, score in rows:
            handle = (profile.twitter_handle or "").lower()
            is_multi_vc = handle in multi_vc_handles
            is_new_follow = profile.id in new_follow_ids

            if not is_multi_vc and not is_new_follow:
                continue

            # Avatar
            avatar = f"https://unavatar.io/twitter/{handle}" if handle else (
                "".join(w[0].upper() for w in (profile.full_name or "?").split()[:2]) or "?"
            )

            # VCs that follow this founder (signals)
            vc_signals = db.query(Signal).filter(
                Signal.profile_id == profile.id,
                Signal.source == "vc_watcher",
                Signal.signal_type.in_(["vc_following", "vc_new_follow"]),
            ).all()
            vc_connections = [
                {
                    "vc": extract_vc_name(s.raw_text),
                    "date": s.created_at.date().isoformat() if s.created_at else "",
                }
                for s in vc_signals
            ]

            # VCs this founder follows (vc_followers table)
            followed_rows = db.query(VcFollower).filter(
                func.lower(VcFollower.username) == handle
            ).all() if handle else []
            followed_vcs = [
                {
                    "vc": WATCHER_NAMES.get(vf.watcher_id, vf.watcher_id),
                    "date": vf.first_seen.date().isoformat() if vf.first_seen else "",
                }
                for vf in followed_rows
            ]

            # For the graph: merge both directions so all edges are drawn
            # followedVCs is what the graph uses for edges
            all_connections = {conn["vc"]: conn for conn in vc_connections}
            for conn in followed_vcs:
                if conn["vc"] not in all_connections:
                    all_connections[conn["vc"]] = conn
            graph_connections = list(all_connections.values())

            total = score.total or 0.0
            activity = activity_from_score(total)
            reasons: list = score.reasons or []
            priority = score.priority or "low"
            fl = score.fundraising_likelihood or "low"
            created_at = profile.created_at
            added_at = created_at.date().isoformat() if created_at else ""
            iso_week = created_at.isocalendar()[1] if created_at else 0

            result.append({
                "id": str(profile.id),
                "name": profile.full_name or f"@{handle}",
                "avatar": avatar,
                "title": profile.role or "",
                "company": profile.company_name_raw or "",
                "country": profile.country or "",
                "sector": infer_sector(profile.bio or profile.headline),
                "score": round(total),
                "scoreExplanation": " · ".join(reasons),
                "scoreSummary": f"{priority.capitalize()} priority · {fl.capitalize()} fundraising likelihood",
                "activity": activity,
                "status": "new",
                "linkedinUrl": profile.linkedin_url or "",
                "xUrl": f"https://x.com/{handle}" if handle else "",
                "vcConnections": vc_connections,   # VCs that follow this founder
                "followedVCs": graph_connections,  # all VC edges for graph
                "lastActivity": created_at.isoformat() if created_at else "",
                "signals": reasons,
                "addedAt": added_at,
                "discoveredWeek": f"W{iso_week}",
                "history": [{"date": added_at, "score": round(total), "activity": activity}] if added_at else [],
            })

        return result

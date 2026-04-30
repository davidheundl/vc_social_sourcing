import json
import re
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.models.scoring import Score
from app.models.relationship import Relationship
from app.services.nlp_extractor import extract_signals


# ---------------------------------------------------------------------------
# Individual dimension scorers
# ---------------------------------------------------------------------------

def score_role(profile: Profile) -> tuple[float, list[str]]:
    text = " ".join(filter(None, [profile.role, profile.headline])).lower()
    reasons = []

    if re.search(r"\bfounder\b|\bco-founder\b|\bcofounder\b", text):
        reasons.append("Founder role detected")
        return 20.0, reasons
    if re.search(r"\bceo\b|\bcto\b|\bcpo\b", text):
        reasons.append("C-level executive")
        return 15.0, reasons
    if re.search(r"\bbuilding\b|\bcreator\b|\bstarting\b", text):
        reasons.append("Building a startup")
        return 12.0, reasons
    if re.search(r"\bemployee\b|\bengineer\b|\bmanager\b", text):
        reasons.append("Startup employee")
        return 6.0, reasons

    return 0.0, reasons


def score_early_stage(profile: Profile) -> tuple[float, list[str]]:
    text = " ".join(filter(None, [profile.bio, profile.headline, profile.recent_posts or ""])).lower()
    signals = extract_signals(text)
    reasons = []

    if not signals.early_stage:
        return 0.0, reasons

    pts = 0.0
    if re.search(r"\bmvp\b|\bbeta\b", text):
        pts = max(pts, 15.0)
        reasons.append("MVP / beta stage mentioned")
    if re.search(r"\bjust started\b|\bnew startup\b|\bstealth\b", text):
        pts = max(pts, 10.0)
        reasons.append("Early / stealth stage signal")
    if re.search(r"\bhiring founding team\b|\bbuilding in public\b", text):
        pts = max(pts, 10.0)
        reasons.append("Hiring founding team / building in public")

    return min(pts, 20.0), reasons


def score_fundraising_intent(profile: Profile) -> tuple[float, list[str]]:
    text = " ".join(filter(None, [profile.bio, profile.headline, profile.recent_posts or ""])).lower()
    reasons = []
    pts = 0.0

    if re.search(r"\braising\b.{0,30}\bseed\b|\bseed round\b|\bpre-?seed\b", text):
        pts = 25.0
        reasons.append("Explicitly raising seed / pre-seed round")
    elif re.search(r"\braising\b|\bfundraising\b|\binvestment round\b", text):
        pts = 20.0
        reasons.append("Fundraising language detected")
    elif re.search(r"\blooking for investors\b|\bopen to investment\b", text):
        pts = 20.0
        reasons.append("Looking for investors")
    elif re.search(r"\btalking to vcs\b|\btalking to investors\b", text):
        pts = 18.0
        reasons.append("Currently talking to VCs")

    return min(pts, 25.0), reasons


def score_network(profile: Profile, db: Session) -> tuple[float, list[str]]:
    reasons = []
    pts = 0.0

    seed_connections = (
        db.query(Relationship)
        .filter(
            Relationship.source_id == profile.id,
            Relationship.rel_type.in_(["follows", "connected_to"]),
        )
        .join(Profile, Profile.id == Relationship.target_id)
        .filter(Profile.is_seed == True)
        .count()
    )

    if seed_connections >= 3:
        pts += 12.0
        reasons.append(f"Connected to {seed_connections} seed VCs / angels")
    elif seed_connections >= 1:
        pts += 8.0
        reasons.append(f"Connected to {seed_connections} seed VC / angel")

    vc_engagements = (
        db.query(Relationship)
        .filter(
            Relationship.source_id == profile.id,
            Relationship.rel_type == "engaged_with",
        )
        .join(Profile, Profile.id == Relationship.target_id)
        .filter(Profile.is_seed == True)
        .count()
    )

    if vc_engagements >= 2:
        pts += 8.0
        reasons.append(f"Engaged with {vc_engagements} VC posts")

    return min(pts, 20.0), reasons


def score_activity(profile: Profile) -> tuple[float, list[str]]:
    if not profile.last_active_at:
        return 0.0, ["No activity data"]

    now = datetime.now(timezone.utc)
    last_active = profile.last_active_at.replace(tzinfo=timezone.utc) \
        if profile.last_active_at.tzinfo is None else profile.last_active_at
    delta_days = (now - last_active).days

    if delta_days <= 7:
        return 10.0, ["Active in the last 7 days"]
    if delta_days <= 30:
        return 7.0, ["Active in the last 30 days"]
    if delta_days <= 90:
        return 3.0, ["Active in the last 3 months"]

    return 0.0, ["Inactive for over 3 months"]


def score_geography(profile: Profile) -> tuple[float, list[str]]:
    EUROPE = {
        "france", "germany", "spain", "italy", "netherlands", "sweden",
        "norway", "denmark", "finland", "switzerland", "austria", "belgium",
        "portugal", "poland", "ireland", "uk", "united kingdom", "czech republic",
        "romania", "hungary", "greece", "europe",
    }
    if profile.country and profile.country.lower() in EUROPE:
        return 5.0, ["Based in Europe"]
    return 0.0, []


# ---------------------------------------------------------------------------
# Main scorer
# ---------------------------------------------------------------------------

def _priority(total: float) -> str:
    if total >= 70:
        return "high"
    if total >= 40:
        return "medium"
    return "low"


def _fundraising_likelihood(fundraising_pts: float) -> str:
    if fundraising_pts >= 20:
        return "high"
    if fundraising_pts >= 10:
        return "medium"
    return "low"


def compute_score(profile: Profile, db: Session) -> Score:
    role_pts, role_reasons = score_role(profile)
    early_pts, early_reasons = score_early_stage(profile)
    fund_pts, fund_reasons = score_fundraising_intent(profile)
    net_pts, net_reasons = score_network(profile, db)
    act_pts, act_reasons = score_activity(profile)
    geo_pts, geo_reasons = score_geography(profile)

    total = role_pts + early_pts + fund_pts + net_pts + act_pts + geo_pts
    all_reasons = role_reasons + early_reasons + fund_reasons + net_reasons + act_reasons + geo_reasons

    existing = db.query(Score).filter(Score.profile_id == profile.id).first()
    score_obj = existing or Score(profile_id=profile.id)

    score_obj.total = round(total, 1)
    score_obj.role_score = role_pts
    score_obj.early_stage_score = early_pts
    score_obj.fundraising_score = fund_pts
    score_obj.network_score = net_pts
    score_obj.activity_score = act_pts
    score_obj.geography_score = geo_pts
    score_obj.reasons = all_reasons
    score_obj.priority = _priority(total)
    score_obj.fundraising_likelihood = _fundraising_likelihood(fund_pts)
    score_obj.scored_at = datetime.utcnow()

    if not existing:
        db.add(score_obj)
    db.commit()
    db.refresh(score_obj)

    return score_obj

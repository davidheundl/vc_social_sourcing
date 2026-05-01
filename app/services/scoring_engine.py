import re
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.models.scoring import Score
from app.models.relationship import Relationship
from app.models.signal import Signal
from app.services.llm_scorer import score_bio

logger = logging.getLogger("scoring_engine")


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------

def score_vc_signals(profile: Profile, db: Session) -> tuple[float, list[str]]:
    """Points for being followed / signaled by watched VCs — primary signal."""
    reasons = []

    # How many distinct VCs follow this person
    vc_follows = (
        db.query(Signal)
        .filter(
            Signal.profile_id == profile.id,
            Signal.source == "vc_watcher",
            Signal.signal_type.in_(["vc_following", "vc_new_follow"]),
        )
        .count()
    )

    # New follow is stronger than just being in the seed list
    new_follow = (
        db.query(Signal)
        .filter(
            Signal.profile_id == profile.id,
            Signal.source == "vc_watcher",
            Signal.signal_type == "vc_new_follow",
        )
        .first()
    )

    pts = 0.0
    if new_follow:
        pts += 30.0
        reasons.append("VC recently started following (new follow)")
    elif vc_follows >= 3:
        pts += 25.0
        reasons.append(f"Followed by {vc_follows} watched VCs")
    elif vc_follows >= 2:
        pts += 18.0
        reasons.append(f"Followed by {vc_follows} watched VCs")
    elif vc_follows == 1:
        pts += 10.0
        reasons.append("Followed by a watched VC")

    return min(pts, 30.0), reasons


def score_role(profile: Profile) -> tuple[float, list[str]]:
    """Infer role from bio + headline + role field."""
    text = " ".join(filter(None, [profile.role, profile.headline, profile.bio])).lower()
    reasons = []

    if re.search(r"\bfounder\b|\bco-?founder\b", text):
        reasons.append("Founder")
        return 20.0, reasons
    if re.search(r"\bceo\b|\bcto\b|\bcpo\b|\bchief\b", text):
        reasons.append("C-level executive")
        return 17.0, reasons
    if re.search(r"\bbuilding\b|\bbuild\b|\blaunching\b|\bcreating\b|\bstarted\b|\bstarting\b", text):
        reasons.append("Building something")
        return 12.0, reasons
    if re.search(r"\bstartup\b|\bventure\b|\bsolopreneur\b|\bindiemaker\b", text):
        reasons.append("Startup context")
        return 10.0, reasons
    if re.search(r"\benginer\b|\bengineer\b|\bdeveloper\b|\bdesigner\b|\bpm\b|\bproduct\b", text):
        reasons.append("Technical / product role")
        return 6.0, reasons

    return 0.0, reasons


def score_early_stage(profile: Profile) -> tuple[float, list[str]]:
    text = " ".join(filter(None, [profile.bio, profile.headline, profile.recent_posts or ""])).lower()
    reasons = []
    pts = 0.0

    if re.search(r"\bmvp\b|\bbeta\b|\bv1\b|\bv0\b|\bshipped\b|\blaunched\b", text):
        pts = max(pts, 15.0)
        reasons.append("Shipped / beta / MVP stage")
    if re.search(r"\bstealth\b|\bjust started\b|\bnew startup\b|\bday \d+\b", text):
        pts = max(pts, 12.0)
        reasons.append("Early / stealth stage")
    if re.search(r"\bbuilding in public\b|\b#buildinpublic\b|\bhiring\b", text):
        pts = max(pts, 10.0)
        reasons.append("Building in public / hiring")
    if re.search(r"\bworking on\b|\bside project\b|\bexperiment\b", text):
        pts = max(pts, 6.0)
        reasons.append("Working on a project")

    return min(pts, 15.0), reasons


def score_fundraising_intent(profile: Profile) -> tuple[float, list[str]]:
    text = " ".join(filter(None, [profile.bio, profile.headline, profile.recent_posts or ""])).lower()
    reasons = []
    pts = 0.0

    if re.search(r"\braising\b.{0,40}\bseed\b|\bseed round\b|\bpre-?seed\b", text):
        pts = 25.0
        reasons.append("Raising seed / pre-seed round")
    elif re.search(r"\braising\b|\bfundraising\b|\bseries [abc]\b", text):
        pts = 20.0
        reasons.append("Fundraising language")
    elif re.search(r"\blooking for investors?\b|\bopen to investment\b|\bopen to funding\b", text):
        pts = 18.0
        reasons.append("Looking for investors")
    elif re.search(r"\btalking to (vcs?|investors?)\b|\bvc-backed\b|\bvc backed\b", text):
        pts = 15.0
        reasons.append("Talking to investors")
    elif re.search(r"\bbootstrapped\b|\bbootstrap\b|\bself-funded\b", text):
        pts = 8.0
        reasons.append("Bootstrapped (self-funded)")

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
        pts += 10.0
        reasons.append(f"Connected to {seed_connections} seed investors")
    elif seed_connections >= 1:
        pts += 6.0
        reasons.append(f"Connected to {seed_connections} seed investor")

    return min(pts, 10.0), reasons


def score_activity(profile: Profile) -> tuple[float, list[str]]:
    if not profile.last_active_at:
        return 0.0, []

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
    return 0.0, []


def score_geography(profile: Profile) -> tuple[float, list[str]]:
    EUROPE = {
        "france", "germany", "spain", "italy", "netherlands", "sweden",
        "norway", "denmark", "finland", "switzerland", "austria", "belgium",
        "portugal", "poland", "ireland", "uk", "united kingdom",
        "czech republic", "romania", "hungary", "greece", "europe",
    }
    if profile.country and profile.country.lower() in EUROPE:
        return 5.0, ["Based in Europe"]
    return 0.0, []


# ---------------------------------------------------------------------------
# Main scorer
# ---------------------------------------------------------------------------

def _priority(total: float) -> str:
    if total >= 45:
        return "high"
    if total >= 20:
        return "medium"
    return "low"


def _fundraising_likelihood(fundraising_pts: float) -> str:
    if fundraising_pts >= 18:
        return "high"
    if fundraising_pts >= 8:
        return "medium"
    return "low"


def compute_score(profile: Profile, db: Session, use_llm: bool = False) -> Score:
    vc_pts,  vc_reasons  = score_vc_signals(profile, db)
    net_pts, net_reasons = score_network(profile, db)
    act_pts, act_reasons = score_activity(profile)
    geo_pts, geo_reasons = score_geography(profile)

    # Bio dimensions: LLM if requested and bio exists, else regex fallback
    if use_llm and profile.bio:
        llm = score_bio(profile.bio)
        if llm:
            role_pts    = float(llm.get("role_score", 0))
            early_pts   = float(llm.get("early_stage_score", 0))
            fund_pts    = float(llm.get("fundraising_score", 0))
            role_reasons  = [llm["role_reason"]]      if llm.get("role_reason")      else []
            early_reasons = [llm["early_stage_reason"]] if llm.get("early_stage_reason") else []
            fund_reasons  = [llm["fundraising_reason"]] if llm.get("fundraising_reason") else []
            logger.info("LLM scored @%s: role=%.0f early=%.0f fund=%.0f",
                        profile.twitter_handle, role_pts, early_pts, fund_pts)
        else:
            # Fallback to regex if LLM call failed
            role_pts,  role_reasons  = score_role(profile)
            early_pts, early_reasons = score_early_stage(profile)
            fund_pts,  fund_reasons  = score_fundraising_intent(profile)
    else:
        role_pts,  role_reasons  = score_role(profile)
        early_pts, early_reasons = score_early_stage(profile)
        fund_pts,  fund_reasons  = score_fundraising_intent(profile)

    total = vc_pts + role_pts + early_pts + fund_pts + net_pts + act_pts + geo_pts
    all_reasons = vc_reasons + role_reasons + early_reasons + fund_reasons + net_reasons + act_reasons + geo_reasons

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

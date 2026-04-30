from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.profile import Profile
from app.models.scoring import Score
from app.schemas.score import ScoreOut, RankedLead
from app.services.scoring_engine import compute_score

router = APIRouter(tags=["scoring"])


@router.post("/score/{profile_id}", response_model=ScoreOut)
def score_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    score = compute_score(profile, db)
    return score


@router.post("/score/all", response_model=dict)
def score_all_profiles(db: Session = Depends(get_db)):
    profiles = db.query(Profile).all()
    for profile in profiles:
        compute_score(profile, db)
    return {"scored": len(profiles)}


@router.get("/ranked-leads", response_model=List[RankedLead])
def ranked_leads(
    min_score: float = Query(0.0),
    country: Optional[str] = Query(None),
    sector: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    limit: int = Query(50),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Profile, Score)
        .join(Score, Score.profile_id == Profile.id)
        .filter(Score.total >= min_score)
    )
    if country:
        q = q.filter(Profile.country.ilike(f"%{country}%"))
    if priority:
        q = q.filter(Score.priority == priority)

    results = q.order_by(Score.total.desc()).limit(limit).all()

    leads = []
    for profile, score in results:
        leads.append(RankedLead(
            id=profile.id,
            full_name=profile.full_name,
            role=profile.role,
            company_name_raw=profile.company_name_raw,
            country=profile.country,
            linkedin_url=profile.linkedin_url,
            twitter_handle=profile.twitter_handle,
            score=score.total,
            priority=score.priority,
            fundraising_likelihood=score.fundraising_likelihood,
            reasons=score.reasons or [],
        ))
    return leads

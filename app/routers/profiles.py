import csv
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.profile import Profile
from app.models.signal import Signal
from app.schemas.profile import ProfileCreate, ProfileOut

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/", response_model=List[ProfileOut])
def list_profiles(
    country: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    is_seed: Optional[bool] = Query(None),
    watcher: Optional[str] = Query(None, description="Filter by VC name, e.g. 'NirkDowztski (test)'"),
    skip: int = 0,
    limit: int = 5000,
    db: Session = Depends(get_db),
):
    q = db.query(Profile)
    if country:
        q = q.filter(Profile.country.ilike(f"%{country}%"))
    if source:
        q = q.filter(Profile.source == source)
    if is_seed is not None:
        q = q.filter(Profile.is_seed == is_seed)
    if watcher:
        q = q.join(Signal, Signal.profile_id == Profile.id).filter(
            Signal.source == "vc_watcher",
            Signal.raw_text.ilike(f"%{watcher}%"),
        ).distinct()
    return q.offset(skip).limit(limit).all()


@router.get("/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.post("/", response_model=ProfileOut, status_code=201)
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)):
    if payload.external_id:
        existing = db.query(Profile).filter(Profile.external_id == payload.external_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Profile already exists")
    profile = Profile(**payload.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/export/csv")
def export_csv(db: Session = Depends(get_db)):
    from app.models.scoring import Score

    rows = (
        db.query(Profile, Score)
        .outerjoin(Score, Score.profile_id == Profile.id)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "full_name", "role", "company", "country",
        "linkedin_url", "twitter_handle", "score", "priority",
        "fundraising_likelihood", "reasons",
    ])
    for profile, score in rows:
        writer.writerow([
            profile.id, profile.full_name, profile.role or "",
            profile.company_name_raw or "", profile.country or "",
            profile.linkedin_url or "", profile.twitter_handle or "",
            score.total if score else "",
            score.priority if score else "",
            score.fundraising_likelihood if score else "",
            "; ".join(score.reasons) if score and score.reasons else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )

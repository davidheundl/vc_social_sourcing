from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.ingest import ingest_batch
from app.schemas.profile import ProfileOut

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/", response_model=List[ProfileOut], status_code=201)
def ingest_profiles(records: List[dict[str, Any]], db: Session = Depends(get_db)):
    if not records:
        raise HTTPException(status_code=422, detail="Empty payload")
    profiles = ingest_batch(records, db)
    return profiles

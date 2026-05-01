from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class ScoreOut(BaseModel):
    profile_id: int
    total: float
    role_score: float
    early_stage_score: float
    fundraising_score: float
    network_score: float
    activity_score: float
    geography_score: float
    reasons: List[str]
    priority: str
    fundraising_likelihood: str
    scored_at: datetime

    model_config = {"from_attributes": True}


class RankedLead(BaseModel):
    id: int
    full_name: str
    role: Optional[str]
    company_name_raw: Optional[str]
    country: Optional[str]
    linkedin_url: Optional[str]
    twitter_handle: Optional[str]
    score: float
    priority: str
    fundraising_likelihood: str
    reasons: List[str]

    model_config = {"from_attributes": True}

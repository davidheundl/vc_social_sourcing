from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CompanyBase(BaseModel):
    name: str
    sector: Optional[str] = None
    stage: Optional[str] = None
    description: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None


class CompanyCreate(CompanyBase):
    pass


class CompanyOut(CompanyBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileBase(BaseModel):
    full_name: str
    headline: Optional[str] = None
    bio: Optional[str] = None
    role: Optional[str] = None
    country: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_handle: Optional[str] = None
    twitter_followers: int = 0
    twitter_following: int = 0
    company_name_raw: Optional[str] = None
    source: Optional[str] = None
    is_seed: bool = False
    external_id: Optional[str] = None
    recent_posts: Optional[str] = None
    last_active_at: Optional[datetime] = None


class ProfileCreate(ProfileBase):
    pass


class ProfileOut(ProfileBase):
    id: int
    company_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

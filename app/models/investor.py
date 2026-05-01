from sqlalchemy import Column, Integer, String, JSON
from app.database import Base


class InvestorProfile(Base):
    __tablename__ = "investor_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    twitter_handle = Column(String(100))
    linkedin_url = Column(String(500))
    investor_type = Column(String(50))  # angel / micro_fund / vc
    focus_areas = Column(JSON)
    location = Column(String(255))

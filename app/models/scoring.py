from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), unique=True, nullable=False)

    # Total
    total = Column(Float, default=0.0)

    # Dimension breakdown (max shown in parentheses)
    role_score = Column(Float, default=0.0)             # /20
    early_stage_score = Column(Float, default=0.0)      # /20
    fundraising_score = Column(Float, default=0.0)      # /25
    network_score = Column(Float, default=0.0)          # /20
    activity_score = Column(Float, default=0.0)         # /10
    geography_score = Column(Float, default=0.0)        # /5

    # Explanation
    reasons = Column(JSON, default=list)                # ["Founder role", "Mentions raising seed"]
    priority = Column(Text, default="low")              # high | medium | low
    fundraising_likelihood = Column(Text, default="low")

    scored_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("Profile", back_populates="score")

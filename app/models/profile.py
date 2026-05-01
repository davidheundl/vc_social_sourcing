from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    sector = Column(String(100))
    stage = Column(String(50))          # pre-seed, seed, series-a
    description = Column(Text)
    country = Column(String(100))
    website = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    profiles = relationship("Profile", back_populates="company")


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(255), unique=True, index=True)  # LinkedIn/X id

    # Identity
    full_name = Column(String(255), nullable=False)
    headline = Column(String(500))
    bio = Column(Text)
    role = Column(String(255))
    country = Column(String(100))

    # Social presence
    linkedin_url = Column(String(500))
    twitter_handle = Column(String(100))
    twitter_followers = Column(Integer, default=0)
    twitter_following = Column(Integer, default=0)

    # Company FK
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    company_name_raw = Column(String(255))   # before normalisation

    # Activity
    last_active_at = Column(DateTime, nullable=True)
    recent_posts = Column(Text)             # JSON string of last N posts

    # Meta
    source = Column(String(50))             # linkedin | twitter | producthunt
    is_seed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="profiles")
    score = relationship("Score", back_populates="profile", uselist=False)
    relationships_out = relationship(
        "Relationship", foreign_keys="Relationship.source_id", back_populates="source"
    )
    relationships_in = relationship(
        "Relationship", foreign_keys="Relationship.target_id", back_populates="target"
    )
    signals = relationship("Signal", back_populates="profile", cascade="all, delete-orphan")

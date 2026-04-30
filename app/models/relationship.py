from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    target_id = Column(Integer, ForeignKey("profiles.id"), nullable=False)

    # follows | works_at_same | commented_on | connected_to | engaged_with
    rel_type = Column(String(50), nullable=False)
    weight = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Profile", foreign_keys=[source_id], back_populates="relationships_out")
    target = relationship("Profile", foreign_keys=[target_id], back_populates="relationships_in")

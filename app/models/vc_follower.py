from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, PrimaryKeyConstraint
from app.database import Base


class VcFollower(Base):
    """
    Stores recent followers of watched VC accounts.
    Only the newest ~200 followers per VC are fetched per scan (reverse-chron order).
    first_seen is set once on insert and never updated — used for the 48h overlap window.
    """
    __tablename__ = "vc_followers"

    watcher_id   = Column(String(64), nullable=False)   # numeric Twitter ID of the VC
    follower_id  = Column(String(64), nullable=False)   # numeric Twitter ID of the follower
    username     = Column(String(100))
    display_name = Column(String(255))
    description  = Column(Text)
    first_seen   = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        PrimaryKeyConstraint("watcher_id", "follower_id"),
    )

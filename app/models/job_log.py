from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database import Base


class JobLog(Base):
    __tablename__ = "job_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(100), unique=True, nullable=False)
    last_run = Column(DateTime(timezone=True))
    last_count = Column(Integer, default=0)
    consecutive_failures = Column(Integer, default=0)
    paused_until = Column(DateTime(timezone=True))


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

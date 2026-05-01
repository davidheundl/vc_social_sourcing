from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator


class FounderStatus(str, Enum):
    new = "new"
    reviewed = "reviewed"
    contacted = "contacted"
    dismissed = "dismissed"


class SignalOut(BaseModel):
    id: int
    founder_id: int
    source: str
    signal_type: str
    raw_text: str | None
    url: str | None
    created_at: str

    @classmethod
    def from_row(cls, row: Any) -> "SignalOut":
        return cls(**dict(row))


class FounderOut(BaseModel):
    id: int
    name: str | None
    twitter_handle: str | None
    linkedin_url: str | None
    github_url: str | None
    score: int
    signals: list[str]
    bio: str | None
    location: str | None
    first_seen: str
    last_updated: str
    status: FounderStatus
    notes: str | None

    @field_validator("signals", mode="before")
    @classmethod
    def parse_signals(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []

    @classmethod
    def from_row(cls, row: Any) -> "FounderOut":
        return cls(**dict(row))


class FounderDetail(FounderOut):
    signal_records: list[SignalOut] = []


class FounderPatch(BaseModel):
    status: FounderStatus | None = None
    notes: str | None = None


class ManualSearchRequest(BaseModel):
    linkedin_url: str


class PaginatedFounders(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[FounderOut]


class StatsOut(BaseModel):
    total_founders: int
    founders_today: int
    average_score: float
    by_source: dict[str, int]


class JobStatus(BaseModel):
    job_name: str
    last_run: str | None
    last_count: int
    consecutive_failures: int
    paused_until: str | None


class HealthOut(BaseModel):
    status: str
    db_counts: dict[str, int]
    jobs: list[JobStatus]

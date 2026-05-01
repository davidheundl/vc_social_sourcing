import sqlite3
import json
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from config import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.sqlite_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL mode for better concurrent read/write
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

CREATE_FOUNDERS = """
CREATE TABLE IF NOT EXISTS founders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT,
    twitter_handle TEXT,
    linkedin_url  TEXT UNIQUE,
    github_url    TEXT,
    score         INTEGER DEFAULT 0,
    signals       TEXT DEFAULT '[]',
    bio           TEXT,
    location      TEXT,
    first_seen    TEXT NOT NULL,
    last_updated  TEXT NOT NULL,
    status        TEXT DEFAULT 'new'
                  CHECK(status IN ('new','reviewed','contacted','dismissed')),
    notes         TEXT DEFAULT ''
)
"""

CREATE_SIGNALS = """
CREATE TABLE IF NOT EXISTS signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    founder_id  INTEGER REFERENCES founders(id) ON DELETE CASCADE,
    source      TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    raw_text    TEXT,
    url         TEXT,
    created_at  TEXT NOT NULL
)
"""

CREATE_INVESTOR_DB = """
CREATE TABLE IF NOT EXISTS investor_db (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    twitter_handle TEXT,
    linkedin_url   TEXT,
    type           TEXT CHECK(type IN ('angel','micro_fund','vc')),
    focus_areas    TEXT DEFAULT '[]',
    location       TEXT
)
"""

CREATE_JOBS_LOG = """
CREATE TABLE IF NOT EXISTS jobs_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name    TEXT UNIQUE NOT NULL,
    last_run    TEXT,
    last_count  INTEGER DEFAULT 0,
    consecutive_failures INTEGER DEFAULT 0,
    paused_until TEXT
)
"""

CREATE_ERRORS = """
CREATE TABLE IF NOT EXISTS errors (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    source     TEXT NOT NULL,
    message    TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""

SEED_INVESTORS = [
    ("Paul Graham", "paulg", "https://linkedin.com/in/paulgraham", "angel", '["b2b","consumer","infra"]', "San Francisco, CA"),
    ("Naval Ravikant", "naval", "https://linkedin.com/in/navalravikant", "angel", '["crypto","saas","consumer"]', "San Francisco, CA"),
    ("Alexis Ohanian", "alexisohanian", "https://linkedin.com/in/alexisohanian", "vc", '["consumer","crypto","social"]', "New York, NY"),
    ("Elad Gil", "eladgil", "https://linkedin.com/in/eladgil", "angel", '["b2b","infra","ai"]', "San Francisco, CA"),
    ("Jason Calacanis", "jason", "https://linkedin.com/in/jasoncalacanis", "angel", '["saas","consumer","fintech"]', "Los Angeles, CA"),
    ("Balaji Srinivasan", "balajis", "https://linkedin.com/in/balajis", "angel", '["crypto","biotech","ai"]', "San Francisco, CA"),
    ("Semil Shah", "semil", "https://linkedin.com/in/semilshah", "micro_fund", '["b2b","consumer","marketplace"]', "San Francisco, CA"),
    ("Brianne Kimmel", "briannekimmel", "https://linkedin.com/in/briannekimmel", "micro_fund", '["saas","future_of_work"]', "San Francisco, CA"),
    ("Harry Stebbings", "hstebbings1996", "https://linkedin.com/in/harrystebbings", "vc", '["b2b","saas","fintech"]', "London, UK"),
    ("Sahil Lavingia", "shl", "https://linkedin.com/in/sahillavingia", "angel", '["saas","creator_economy"]', "Remote"),
]


def init_db():
    with get_db() as conn:
        conn.execute(CREATE_FOUNDERS)
        conn.execute(CREATE_SIGNALS)
        conn.execute(CREATE_INVESTOR_DB)
        conn.execute(CREATE_JOBS_LOG)
        conn.execute(CREATE_ERRORS)

        # Seed investors only if table is empty
        count = conn.execute("SELECT COUNT(*) FROM investor_db").fetchone()[0]
        if count == 0:
            conn.executemany(
                """INSERT INTO investor_db (name, twitter_handle, linkedin_url, type, focus_areas, location)
                   VALUES (?,?,?,?,?,?)""",
                SEED_INVESTORS,
            )
            logger.info("Seeded investor_db with %d example angels/VCs", len(SEED_INVESTORS))

        # Seed jobs_log entries so health endpoint always has rows
        for job in ("twitter_crawler", "google_dorker", "proxycurl_enricher",
                    "producthunt_crawler", "hackernews_crawler", "social_lookup",
                    "scoring_refresh"):
            conn.execute(
                "INSERT OR IGNORE INTO jobs_log (job_name) VALUES (?)", (job,)
            )

    logger.info("Database initialised at %s", config.sqlite_path)


# ---------------------------------------------------------------------------
# Utility helpers used by multiple modules
# ---------------------------------------------------------------------------

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_founder(conn: sqlite3.Connection, *, twitter_handle: str | None = None,
                   linkedin_url: str | None = None, name: str | None = None,
                   bio: str | None = None, location: str | None = None,
                   github_url: str | None = None) -> int:
    """
    Insert a new founder or return the existing id.
    linkedin_url is the primary dedup key; twitter_handle is the fallback.
    Returns the founder id.
    """
    now = utcnow()

    # Try to find by linkedin_url first, then twitter_handle
    existing = None
    if linkedin_url:
        existing = conn.execute(
            "SELECT id FROM founders WHERE linkedin_url = ?", (linkedin_url,)
        ).fetchone()
    if existing is None and twitter_handle:
        existing = conn.execute(
            "SELECT id FROM founders WHERE twitter_handle = ?", (twitter_handle,)
        ).fetchone()

    if existing:
        fid = existing["id"]
        # Update fields that were previously unknown
        updates = []
        params: list = []
        if name:
            updates.append("name = COALESCE(NULLIF(name,''), ?)")
            params.append(name)
        if bio:
            updates.append("bio = COALESCE(NULLIF(bio,''), ?)")
            params.append(bio)
        if location:
            updates.append("location = COALESCE(NULLIF(location,''), ?)")
            params.append(location)
        if linkedin_url:
            updates.append("linkedin_url = COALESCE(NULLIF(linkedin_url,''), ?)")
            params.append(linkedin_url)
        if github_url:
            updates.append("github_url = COALESCE(NULLIF(github_url,''), ?)")
            params.append(github_url)
        if twitter_handle:
            updates.append("twitter_handle = COALESCE(NULLIF(twitter_handle,''), ?)")
            params.append(twitter_handle)
        if updates:
            updates.append("last_updated = ?")
            params.append(now)
            params.append(fid)
            conn.execute(f"UPDATE founders SET {', '.join(updates)} WHERE id = ?", params)
        return fid

    # Insert new founder
    cursor = conn.execute(
        """INSERT INTO founders (name, twitter_handle, linkedin_url, github_url, bio, location,
                                 first_seen, last_updated)
           VALUES (?,?,?,?,?,?,?,?)""",
        (name, twitter_handle, linkedin_url, github_url, bio, location, now, now),
    )
    return cursor.lastrowid


def add_signal(conn: sqlite3.Connection, *, founder_id: int, source: str,
               signal_type: str, raw_text: str | None = None,
               url: str | None = None) -> None:
    conn.execute(
        """INSERT INTO signals (founder_id, source, signal_type, raw_text, url, created_at)
           VALUES (?,?,?,?,?,?)""",
        (founder_id, source, signal_type, raw_text, url, utcnow()),
    )
    # Append source to founder's signals JSON array
    row = conn.execute("SELECT signals FROM founders WHERE id = ?", (founder_id,)).fetchone()
    if row:
        current: list = json.loads(row["signals"] or "[]")
        if source not in current:
            current.append(source)
        conn.execute(
            "UPDATE founders SET signals = ?, last_updated = ? WHERE id = ?",
            (json.dumps(current), utcnow(), founder_id),
        )


def log_job(conn: sqlite3.Connection, job_name: str, count: int,
            failed: bool = False) -> None:
    now = utcnow()
    if failed:
        conn.execute(
            """UPDATE jobs_log
               SET last_run = ?,
                   consecutive_failures = consecutive_failures + 1
               WHERE job_name = ?""",
            (now, job_name),
        )
    else:
        conn.execute(
            """UPDATE jobs_log
               SET last_run = ?, last_count = ?, consecutive_failures = 0, paused_until = NULL
               WHERE job_name = ?""",
            (now, count, job_name),
        )


def log_error(conn: sqlite3.Connection, source: str, message: str) -> None:
    conn.execute(
        "INSERT INTO errors (source, message, created_at) VALUES (?,?,?)",
        (source, message, utcnow()),
    )


def is_investor(conn: sqlite3.Connection, twitter_handle: str | None = None,
                linkedin_url: str | None = None) -> bool:
    if twitter_handle:
        row = conn.execute(
            "SELECT id FROM investor_db WHERE twitter_handle = ?", (twitter_handle,)
        ).fetchone()
        if row:
            return True
    if linkedin_url:
        row = conn.execute(
            "SELECT id FROM investor_db WHERE linkedin_url = ?", (linkedin_url,)
        ).fetchone()
        if row:
            return True
    return False

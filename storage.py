import sqlite3
from contextlib import contextmanager
from config import DB_PATH


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS following (
                watcher_id   TEXT NOT NULL,   -- the VC account we're watching
                followed_id  TEXT NOT NULL,   -- account they follow
                username     TEXT,
                display_name TEXT,
                description  TEXT,
                first_seen   TEXT DEFAULT (datetime('now')),
                ai_score     INTEGER,         -- 0-10 founder potential score
                ai_reason    TEXT,            -- one-line explanation
                ai_tags      TEXT,            -- comma-separated tags
                PRIMARY KEY (watcher_id, followed_id)
            );

            CREATE TABLE IF NOT EXISTS new_signals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                watcher_id   TEXT NOT NULL,
                watcher_name TEXT,
                followed_id  TEXT NOT NULL,
                username     TEXT,
                display_name TEXT,
                description  TEXT,
                detected_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS vc_followers (
                watcher_id   TEXT NOT NULL,
                follower_id  TEXT NOT NULL,
                username     TEXT,
                display_name TEXT,
                description  TEXT,
                first_seen   TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (watcher_id, follower_id)
            );
        """)


def get_known_following(watcher_id: str) -> set[str]:
    """Return set of followed user IDs we already know about."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT followed_id FROM following WHERE watcher_id = ?", (watcher_id,)
        ).fetchall()
    return {r["followed_id"] for r in rows}


def save_following(watcher_id: str, users: list[dict]):
    """Upsert the full following list for a watcher."""
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO following (watcher_id, followed_id, username, display_name, description)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(watcher_id, followed_id) DO UPDATE SET
                username     = excluded.username,
                display_name = excluded.display_name,
                description  = excluded.description
            """,
            [
                (watcher_id, u["id"], u["username"], u["name"], u.get("description", ""))
                for u in users
            ],
        )


def save_signals(watcher_id: str, watcher_name: str, new_users: list[dict]):
    """Persist newly detected follows as signals."""
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO new_signals (watcher_id, watcher_name, followed_id, username, display_name, description)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (watcher_id, watcher_name, u["id"], u["username"], u["name"], u.get("description", ""))
                for u in new_users
            ],
        )


def save_vc_followers(watcher_id: str, users: list[dict]):
    """Upsert recent followers of a VC. first_seen is only set on first insert."""
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO vc_followers (watcher_id, follower_id, username, display_name, description)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(watcher_id, follower_id) DO UPDATE SET
                username     = excluded.username,
                display_name = excluded.display_name,
                description  = excluded.description
            """,
            [
                (watcher_id, u["id"], u["username"], u["name"], u.get("description", ""))
                for u in users
            ],
        )


def get_multi_vc_followers(min_overlap: int = 3, window_hours: int = 48) -> list[sqlite3.Row]:
    """Return people who followed min_overlap or more VCs within the time window."""
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT
                follower_id,
                username,
                display_name,
                description,
                COUNT(DISTINCT watcher_id)        AS vc_count,
                GROUP_CONCAT(DISTINCT watcher_id) AS watcher_ids,
                MIN(first_seen)                   AS first_seen
            FROM vc_followers
            WHERE first_seen >= datetime('now', ? || ' hours')
            GROUP BY follower_id
            HAVING vc_count >= ?
            ORDER BY vc_count DESC, first_seen DESC
            """,
            (f"-{window_hours}", min_overlap),
        ).fetchall()


def get_recent_signals(limit: int = 50) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT * FROM new_signals
            ORDER BY detected_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

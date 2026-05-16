import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tweets (
    id INTEGER PRIMARY KEY,
    drafted_at TIMESTAMP NOT NULL,
    posted_at TIMESTAMP,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    twitter_id TEXT,
    twitter_url TEXT,
    confidence REAL,
    angle TEXT,
    source_commits JSON
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY,
    ran_at TIMESTAMP NOT NULL,
    should_post BOOLEAN NOT NULL,
    mood TEXT,
    reasoning TEXT,
    commit_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_tweets_status ON tweets(status);
CREATE INDEX IF NOT EXISTS idx_tweets_posted_at ON tweets(posted_at);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(_SCHEMA)


def save_pending_drafts(drafts: list[dict], source_commits: list[Any]) -> list[int]:
    now = datetime.now(timezone.utc).isoformat()
    commits_json = json.dumps([c.__dict__ if hasattr(c, "__dict__") else c for c in source_commits], default=str)
    ids = []
    with _conn() as conn:
        for draft in drafts:
            cur = conn.execute(
                "INSERT INTO tweets (drafted_at, text, status, confidence, angle, source_commits) VALUES (?, ?, 'pending', ?, ?, ?)",
                (now, draft["tweet"], draft["confidence"], draft["angle"], commits_json),
            )
            ids.append(cur.lastrowid)
    return ids


def get_recent_posted_tweets(days: int = 7) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT text, posted_at, angle FROM tweets WHERE status IN ('posted', 'edited') AND posted_at >= ? ORDER BY posted_at DESC",
            (cutoff,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_pending_drafts() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, text, confidence, angle, drafted_at FROM tweets WHERE status = 'pending' ORDER BY confidence DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def mark_posted(draft_id: int, twitter_id: str, twitter_url: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE tweets SET status = 'posted', posted_at = ?, twitter_id = ?, twitter_url = ? WHERE id = ?",
            (now, twitter_id, twitter_url, draft_id),
        )


def mark_edited_and_posted(draft_id: int, new_text: str, twitter_id: str, twitter_url: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "UPDATE tweets SET status = 'edited', text = ?, posted_at = ?, twitter_id = ?, twitter_url = ? WHERE id = ?",
            (new_text, now, twitter_id, twitter_url, draft_id),
        )


def mark_skipped(draft_id: int | None = None) -> None:
    with _conn() as conn:
        if draft_id is not None:
            conn.execute("UPDATE tweets SET status = 'skipped' WHERE id = ?", (draft_id,))
        else:
            conn.execute("UPDATE tweets SET status = 'skipped' WHERE status = 'pending'")


def mark_expired_drafts() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=config.DRAFT_EXPIRY_HOURS)).isoformat()
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE tweets SET status = 'expired' WHERE status = 'pending' AND drafted_at <= ?",
            (cutoff,),
        )
        return cur.rowcount


def log_decision(should_post: bool, mood: str | None, reasoning: str | None, commit_count: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO decisions (ran_at, should_post, mood, reasoning, commit_count) VALUES (?, ?, ?, ?, ?)",
            (now, should_post, mood, reasoning, commit_count),
        )


init_db()

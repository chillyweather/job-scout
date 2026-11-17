"""SQLite state: which postings were seen, when, and which boards are failing."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    key TEXT PRIMARY KEY,
    board_key TEXT NOT NULL,
    company TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    closed_at TEXT,
    reported_at TEXT,
    reported_hash TEXT
);
CREATE INDEX IF NOT EXISTS postings_board ON postings(board_key);
CREATE TABLE IF NOT EXISTS boards (
    board_key TEXT PRIMARY KEY,
    first_ok TEXT,
    last_ok TEXT,
    last_error TEXT,
    last_error_at TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0
);
"""


class State:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    # boards

    def board_seen_before(self, board_key: str) -> bool:
        row = self.db.execute("SELECT first_ok FROM boards WHERE board_key = ?", (board_key,)).fetchone()
        return bool(row and row["first_ok"])

    def board_ok(self, board_key: str, now: str) -> None:
        self.db.execute(
            """INSERT INTO boards (board_key, first_ok, last_ok, consecutive_failures) VALUES (?, ?, ?, 0)
               ON CONFLICT(board_key) DO UPDATE SET
                 first_ok = COALESCE(boards.first_ok, excluded.first_ok),
                 last_ok = excluded.last_ok, consecutive_failures = 0""",
            (board_key, now, now),
        )

    def board_failed(self, board_key: str, error: str, now: str) -> int:
        self.db.execute(
            """INSERT INTO boards (board_key, last_error, last_error_at, consecutive_failures) VALUES (?, ?, ?, 1)
               ON CONFLICT(board_key) DO UPDATE SET
                 last_error = excluded.last_error, last_error_at = excluded.last_error_at,
                 consecutive_failures = boards.consecutive_failures + 1""",
            (board_key, error, now),
        )
        row = self.db.execute(
            "SELECT consecutive_failures FROM boards WHERE board_key = ?", (board_key,)
        ).fetchone()
        return int(row["consecutive_failures"])

    # postings

    def get(self, key: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM postings WHERE key = ?", (key,)).fetchone()

    def upsert(self, key: str, board_key: str, company: str, title: str, url: str, content_hash: str, now: str) -> None:
        self.db.execute(
            """INSERT INTO postings (key, board_key, company, title, url, content_hash, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET
                 title = excluded.title, url = excluded.url, content_hash = excluded.content_hash,
                 last_seen = excluded.last_seen, closed_at = NULL""",
            (key, board_key, company, title, url, content_hash, now, now),
        )

    def mark_reported(self, key: str, content_hash: str, now: str) -> None:
        self.db.execute(
            "UPDATE postings SET reported_at = ?, reported_hash = ? WHERE key = ?", (now, content_hash, key)
        )

    def close_missing(self, board_key: str, present_keys: set[str], now: str) -> list[sqlite3.Row]:
        rows = self.db.execute(
            "SELECT * FROM postings WHERE board_key = ? AND closed_at IS NULL", (board_key,)
        ).fetchall()
        gone = [row for row in rows if row["key"] not in present_keys]
        self.db.executemany(
            "UPDATE postings SET closed_at = ? WHERE key = ?", [(now, row["key"]) for row in gone]
        )
        return gone

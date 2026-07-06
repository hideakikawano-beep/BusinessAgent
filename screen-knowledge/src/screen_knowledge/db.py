"""SQLite access: pragmas, migrations, single-writer discipline.

Rules (docs/02-architecture.md "書き込み規律"):
- Every connection sets: journal_mode=WAL, synchronous=NORMAL,
  busy_timeout=5000, foreign_keys=ON.
- The daemon process funnels ALL writes through `Database.write()` — a single
  connection guarded by a threading.Lock. Keep transactions < 100ms.
- The viewer opens read-only connections (`open_readonly()`), short-lived per
  request.
- migrate() creates the FULL schema from docs/03-data-model.md (including
  tables unused until later phases), versioned via settings.schema_version.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

SCHEMA_VERSION = 1

# Full DDL — keep in sync with docs/03-data-model.md.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id                 INTEGER PRIMARY KEY,
  started_at         TEXT NOT NULL,
  ended_at           TEXT NOT NULL,
  app_name           TEXT NOT NULL,
  title_sample       TEXT,
  frame_count        INTEGER NOT NULL,
  stored_frame_count INTEGER NOT NULL,
  is_marked          INTEGER NOT NULL DEFAULT 0,
  status             TEXT NOT NULL DEFAULT 'captured',
  batch_id           TEXT,
  fail_reason        TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_status  ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);

CREATE TABLE IF NOT EXISTS frames (
  id            INTEGER PRIMARY KEY,
  captured_at   TEXT NOT NULL,
  app_name      TEXT NOT NULL DEFAULT '',
  window_title  TEXT NOT NULL DEFAULT '',
  monitor_index INTEGER,
  phash         TEXT,
  image_path    TEXT,
  stored_reason TEXT,
  skipped_reason TEXT,
  is_marked     INTEGER NOT NULL DEFAULT 0,
  session_id    INTEGER REFERENCES sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_frames_time    ON frames(captured_at);
CREATE INDEX IF NOT EXISTS idx_frames_session ON frames(session_id);

CREATE TABLE IF NOT EXISTS marks (
  id         INTEGER PRIMARY KEY,
  started_at TEXT NOT NULL,
  ended_at   TEXT,
  note       TEXT
);

CREATE TABLE IF NOT EXISTS session_analyses (
  id                 INTEGER PRIMARY KEY,
  session_id         INTEGER NOT NULL UNIQUE REFERENCES sessions(id),
  model              TEXT NOT NULL,
  analyzed_at        TEXT NOT NULL,
  task_label         TEXT NOT NULL,
  task_category      TEXT NOT NULL,
  summary            TEXT NOT NULL,
  steps_json         TEXT NOT NULL,
  notable_facts_json TEXT NOT NULL DEFAULT '[]',
  worth_documenting  INTEGER NOT NULL,
  confidence         TEXT NOT NULL,
  input_tokens       INTEGER,
  output_tokens      INTEGER
);

CREATE TABLE IF NOT EXISTS manuals (
  id                       INTEGER PRIMARY KEY,
  slug                     TEXT NOT NULL UNIQUE,
  title                    TEXT NOT NULL,
  file_path                TEXT NOT NULL,
  status                   TEXT NOT NULL DEFAULT 'draft',
  revision                 INTEGER NOT NULL DEFAULT 1,
  summary                  TEXT NOT NULL DEFAULT '',
  source_session_ids_json  TEXT NOT NULL DEFAULT '[]',
  created_at               TEXT NOT NULL,
  updated_at               TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_logs (
  date       TEXT PRIMARY KEY,
  file_path  TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_usage (
  id                INTEGER PRIMARY KEY,
  ts                TEXT NOT NULL,
  kind              TEXT NOT NULL,
  model             TEXT NOT NULL,
  is_batch          INTEGER NOT NULL DEFAULT 0,
  request_id        TEXT,
  batch_id          TEXT,
  input_tokens      INTEGER NOT NULL,
  output_tokens     INTEGER NOT NULL,
  cache_read_tokens INTEGER NOT NULL DEFAULT 0,
  cost_usd          REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_ts ON api_usage(ts);
"""

# FTS5 external table (Phase 4). Created separately because it can fail on
# builds without the trigram tokenizer; doctor reports availability.
_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(
  title, body,
  doc_type UNINDEXED,
  ref_id   UNINDEXED,
  tokenize='trigram'
);
"""

Row = dict[str, Any]


def apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")


def _rows(cur: sqlite3.Cursor) -> list[Row]:
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, r, strict=False)) for r in cur.fetchall()]


class Database:
    """Owner of the writer connection (one instance per daemon process)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        apply_pragmas(self._conn)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def migrate(self) -> None:
        """Create/upgrade schema idempotently (all tables from docs/03)."""
        with self._lock:
            self._conn.executescript(_SCHEMA)
            try:
                self._conn.executescript(_FTS_SCHEMA)
            except sqlite3.OperationalError:
                # trigram unavailable on this build; Phase 4 falls back to LIKE.
                pass
            self._conn.execute(
                "INSERT INTO settings(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            self._conn.commit()

    # -- generic helpers --
    def write(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        with self._lock:
            result = fn(self._conn)
            self._conn.commit()
            return result

    def read(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        with self._lock:
            return fn(self._conn)

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        self.write(lambda c: c.execute(sql, params))

    def insert(self, table: str, data: Row) -> int:
        cols = ", ".join(data)
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        values = list(data.values())
        return self.write(lambda c: c.execute(sql, values).lastrowid)

    def query(self, sql: str, params: Sequence[Any] = ()) -> list[Row]:
        return self.read(lambda c: _rows(c.execute(sql, params)))

    def query_one(self, sql: str, params: Sequence[Any] = ()) -> Row | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        row = self.read(lambda c: c.execute(sql, params).fetchone())
        return row[0] if row else None

    # -- settings helpers (heartbeat, paused_until, mark_active, ...) --
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.query_one("SELECT value FROM settings WHERE key=?", (key,))
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

    def backup(self, dest: Path) -> None:
        """Online backup API copy (used by `sk backup`)."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            target = sqlite3.connect(str(dest))
            try:
                self._conn.backup(target)
            finally:
                target.close()


def open_readonly(path: Path) -> sqlite3.Connection:
    """Read-only connection for the viewer process (mode=ro URI)."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def fts5_trigram_available(conn: sqlite3.Connection) -> bool:
    """Doctor check: FTS5 with tokenize='trigram' (SQLite >= 3.34)."""
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE temp._sk_fts_probe USING fts5(x, tokenize='trigram')"
        )
        conn.execute("DROP TABLE temp._sk_fts_probe")
        return True
    except sqlite3.OperationalError:
        return False

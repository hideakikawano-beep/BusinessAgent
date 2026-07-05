"""SQLite access: pragmas, migrations, single-writer discipline.

Rules (docs/02-architecture.md "書き込み規律"):
- Every connection sets: journal_mode=WAL, synchronous=NORMAL,
  busy_timeout=5000, foreign_keys=ON.
- The daemon process funnels ALL writes through `Database.write()` — a single
  connection guarded by a threading.Lock. Keep transactions < 100ms.
- The viewer opens read-only connections (`open_readonly()`), short-lived per
  request.
- Migrations create the FULL schema from docs/03-data-model.md (including
  tables unused until later phases) and are versioned via settings.schema_version.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

# Full DDL lives in docs/03-data-model.md — keep this constant in sync with it.
SCHEMA_VERSION = 1


class Database:
    """Owner of the writer connection (one instance per daemon process)."""

    def __init__(self, path: Path) -> None:
        raise NotImplementedError("Phase 1")

    def migrate(self) -> None:
        """Create/upgrade schema idempotently (all tables from docs/03)."""
        raise NotImplementedError("Phase 1")

    def write(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Run `fn` on the writer connection under the writer lock, commit."""
        raise NotImplementedError("Phase 1")

    def read(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Run a read-only query on the writer process's connection."""
        raise NotImplementedError("Phase 1")

    def backup(self, dest: Path) -> None:
        """Online backup API copy (used by `sk backup`)."""
        raise NotImplementedError("Phase 1")

    # -- settings helpers (heartbeat, paused_until, mark_active, ...) --
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        raise NotImplementedError("Phase 1")

    def set_setting(self, key: str, value: str) -> None:
        raise NotImplementedError("Phase 1")


def open_readonly(path: Path) -> sqlite3.Connection:
    """Read-only connection for the viewer process (mode=ro URI)."""
    raise NotImplementedError("Phase 1")


def apply_pragmas(conn: sqlite3.Connection) -> None:
    raise NotImplementedError("Phase 1")


def fts5_trigram_available(conn: sqlite3.Connection) -> bool:
    """Doctor check: FTS5 with tokenize='trigram' (SQLite >= 3.34)."""
    raise NotImplementedError("Phase 1")


Row = dict[str, Any]  # convention: query helpers return plain dict rows

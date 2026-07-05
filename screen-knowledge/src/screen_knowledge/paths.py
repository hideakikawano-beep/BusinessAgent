"""Resolution of all filesystem locations under ~/ScreenKnowledge/.

This module is the ONLY place that knows the data root. Tests override the
root via `set_root()` (see tests/conftest.py) so the real home directory is
never touched.

Layout (docs/03-data-model.md):
    <root>/config.yaml
    <root>/data/index.sqlite3
    <root>/shots/YYYY/MM/DD/<frame_id>.webp
    <root>/vault/{manuals,knowledge,daily}
    <root>/logs/daemon.log
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

_root_override: Path | None = None


def set_root(path: Path | None) -> None:
    """Override the data root (tests only)."""
    global _root_override
    _root_override = path


def root() -> Path:
    """Return the data root, creating nothing."""
    if _root_override is not None:
        return _root_override
    return Path.home() / "ScreenKnowledge"


def config_file() -> Path:
    return root() / "config.yaml"


def db_file() -> Path:
    return root() / "data" / "index.sqlite3"


def shots_dir(when: dt.date | None = None) -> Path:
    """shots/ root, or the YYYY/MM/DD subdirectory for `when`."""
    base = root() / "shots"
    if when is None:
        return base
    return base / f"{when:%Y}" / f"{when:%m}" / f"{when:%d}"


def vault_dir() -> Path:
    return root() / "vault"


def manuals_dir() -> Path:
    return vault_dir() / "manuals"


def manual_assets_dir(slug: str) -> Path:
    return manuals_dir() / "assets" / slug


def knowledge_dir() -> Path:
    return vault_dir() / "knowledge"


def daily_dir() -> Path:
    return vault_dir() / "daily"


def logs_dir() -> Path:
    return root() / "logs"


def ensure_layout() -> None:
    """Create the directory skeleton (idempotent). Called by `sk start`."""
    raise NotImplementedError("Phase 1")

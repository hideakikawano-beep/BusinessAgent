"""WebP storage and retention purge (Phase 1).

- save path: shots/YYYY/MM/DD/<frame_id>.webp  (paths.shots_dir)
- downscale long edge to capture.store_long_edge_px, WebP quality ~80
- purge scope is shots/ ONLY — vault/manuals/assets/ is exempt (docs/03)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PurgeReport:
    deleted_files: int = 0
    freed_bytes: int = 0
    deleted_meta_rows: int = 0
    dry_run: bool = False
    details: list[str] = field(default_factory=list)


class FrameStore:
    def __init__(self, cfg, db) -> None:  # config.Config, db.Database
        raise NotImplementedError("Phase 1")

    def save_webp(self, img, frame_id: int, when: dt.datetime) -> Path:
        raise NotImplementedError("Phase 1")

    def purge(
        self,
        older_than_days: int,
        max_gb: float,
        *,
        metadata_days: int,
        dry_run: bool = False,
    ) -> PurgeReport:
        """Delete images past retention, then oldest-first down to max_gb;
        delete metadata rows past metadata_days. Never touches vault/."""
        raise NotImplementedError("Phase 1")

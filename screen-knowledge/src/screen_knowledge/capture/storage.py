"""WebP storage and retention purge (Phase 1).

- save path: shots/YYYY/MM/DD/<frame_id>.webp  (paths.shots_dir)
- downscale long edge to capture.store_long_edge_px, WebP quality ~80
- purge scope is shots/ ONLY — vault/manuals/assets/ is exempt (docs/03)
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .. import paths

if TYPE_CHECKING:  # pragma: no cover
    import PIL.Image

    from ..config import Config
    from ..db import Database


@dataclass
class PurgeReport:
    deleted_files: int = 0
    freed_bytes: int = 0
    deleted_meta_rows: int = 0
    dry_run: bool = False
    details: list[str] = field(default_factory=list)


def downscale(img: PIL.Image.Image, long_edge_px: int) -> PIL.Image.Image:
    """Return a copy scaled so its long edge is <= long_edge_px (no upscaling)."""
    w, h = img.size
    longest = max(w, h)
    if longest <= long_edge_px:
        return img
    scale = long_edge_px / longest
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))))


class FrameStore:
    def __init__(self, cfg: Config, db: Database) -> None:
        self.cfg = cfg
        self.db = db

    def save_webp(self, img: PIL.Image.Image, frame_id: int, when: dt.datetime) -> Path:
        """Downscale to store_long_edge_px and write shots/YYYY/MM/DD/<id>.webp.

        Returns the absolute path; the caller records the path relative to
        shots/ in frames.image_path.
        """
        out_dir = paths.shots_dir(when.date())
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{frame_id}.webp"
        scaled = downscale(img, self.cfg.capture.store_long_edge_px)
        if scaled.mode not in ("RGB", "RGBA"):
            scaled = scaled.convert("RGB")
        scaled.save(out, format="WEBP", quality=80, method=4)
        return out

    @staticmethod
    def relpath(abs_path: Path) -> str:
        return str(abs_path.relative_to(paths.shots_dir()))

    def _shots_files(self) -> list[Path]:
        base = paths.shots_dir()
        if not base.exists():
            return []
        return [p for p in base.rglob("*.webp") if p.is_file()]

    def purge(
        self,
        older_than_days: int,
        max_gb: float,
        *,
        metadata_days: int,
        dry_run: bool = False,
        now: dt.datetime | None = None,
    ) -> PurgeReport:
        """Delete images past retention, then oldest-first down to max_gb;
        delete metadata rows past metadata_days. Never touches vault/."""
        now = now or dt.datetime.now().astimezone()
        report = PurgeReport(dry_run=dry_run)
        shots_root = paths.shots_dir()

        files = self._shots_files()
        # (path, mtime, size)
        stat = [(p, p.stat().st_mtime, p.stat().st_size) for p in files]

        age_cutoff = (now - dt.timedelta(days=older_than_days)).timestamp()
        remaining: list[tuple[Path, float, int]] = []
        for p, mtime, size in stat:
            if mtime < age_cutoff:
                self._delete_image(p, size, report, dry_run)
            else:
                remaining.append((p, mtime, size))

        # Enforce max_gb over what survived the age purge (oldest first).
        max_bytes = int(max_gb * 1024**3)
        total = sum(s for _, _, s in remaining)
        if total > max_bytes:
            for p, _mtime, size in sorted(remaining, key=lambda t: t[1]):
                if total <= max_bytes:
                    break
                self._delete_image(p, size, report, dry_run)
                total -= size

        # Delete metadata rows past metadata_days.
        meta_cutoff = (now - dt.timedelta(days=metadata_days)).isoformat()
        count = self.db.scalar(
            "SELECT COUNT(*) FROM frames WHERE captured_at < ?", (meta_cutoff,)
        ) or 0
        report.deleted_meta_rows = int(count)
        if not dry_run and count:
            self.db.execute("DELETE FROM frames WHERE captured_at < ?", (meta_cutoff,))

        _ = shots_root  # (kept for clarity; deletions above are within it)
        return report

    def _delete_image(
        self, p: Path, size: int, report: PurgeReport, dry_run: bool
    ) -> None:
        rel = None
        try:
            rel = str(p.relative_to(paths.shots_dir()))
        except ValueError:
            rel = str(p)
        report.deleted_files += 1
        report.freed_bytes += size
        report.details.append(rel)
        if dry_run:
            return
        p.unlink(missing_ok=True)
        # Reflect deletion in the DB so the viewer shows a placeholder.
        self.db.execute("UPDATE frames SET image_path=NULL WHERE image_path=?", (rel,))

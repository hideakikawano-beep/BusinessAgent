"""Session boundary detection (Phase 2). `group_frames` is a PURE function.

Boundary rules (docs/02 解析パイプライン):
- app continuity with interruption tolerance: an excursion to another app
  shorter than interruption_tolerance_s (60s) does NOT close the session and
  its frames attach to the dominant session
- close on: app change persisting > tolerance, recording gap > gap_s (120s),
  idle split, daemon stop
- browser sessions are NOT split per tab (title sequence goes to the LLM)
- sessions overlapping an open/closed mark interval get is_marked=1
- sessions with fewer than analysis.min_session_ticks frames -> status='skipped'
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

FrameRow = dict[str, Any]  # row from frames table (db.Row)


@dataclass
class SessionDraft:
    started_at: str
    ended_at: str
    app_name: str
    title_sample: str | None
    frame_ids: list[int] = field(default_factory=list)
    is_marked: bool = False


def group_frames(
    frames: list[FrameRow],
    *,
    gap_s: int,
    interruption_tolerance_s: int,
) -> list[SessionDraft]:
    """Pure function: ordered frames -> session drafts (no DB access)."""
    raise NotImplementedError("Phase 2")


def run_sessionizer(db, cfg) -> int:
    """Scan frames with session_id IS NULL, persist sessions, assign
    frames.session_id, mark skipped sessions. Returns #sessions created.
    Runs every 5 min in the scheduler worker."""
    raise NotImplementedError("Phase 2")

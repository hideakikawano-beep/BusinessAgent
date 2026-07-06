"""Manual matcher — update-vs-create decision (Phase 3).

Uses api.analysis_model (cheap) with schemas.MatchResult. Catalog = manuals
(title + summary) where status != 'archived'. LOW confidence maps to None:
a duplicate draft is safer than corrupting an existing manual (docs/00 #10).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ManualSummary:
    manual_id: int
    title: str
    summary: str


class ManualMatcher:
    def __init__(self, cfg, client) -> None:
        raise NotImplementedError("Phase 3")

    def find_match(self, analysis, catalog: list[ManualSummary]) -> int | None:
        raise NotImplementedError("Phase 3")

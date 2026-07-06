"""FTS5 search index (Phase 4).

- table search_fts (docs/03): tokenize='trigram' — REQUIRED for Japanese
  substring search; fall back to LIKE when unavailable (search_degraded=True)
- writes happen on the DAEMON side (upsert hooked into vault writes);
  the viewer process only reads
- sk reindex rebuilds from vault (mtime scan; also ingests hand-edited md)
  and session_analyses
- query safety: wrap user input as an FTS phrase ("..."), fall back to LIKE
  on syntax errors; queries shorter than 3 chars use LIKE (trigram limit)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DocType = Literal["manual", "knowledge", "daily", "session"]


@dataclass
class SearchHit:
    doc_type: DocType
    ref_id: str
    title: str
    snippet_html: str  # <mark> highlighted
    score: float


class SearchIndex:
    def __init__(self, db) -> None:
        raise NotImplementedError("Phase 4")

    def reindex_all(self) -> int:
        raise NotImplementedError("Phase 4")

    def upsert(self, doc_type: DocType, ref_id: str, title: str, body: str) -> None:
        raise NotImplementedError("Phase 4")

    def search(
        self, q: str, *, doc_type: DocType | None = None, limit: int = 30
    ) -> tuple[list[SearchHit], bool]:
        """Returns (hits, search_degraded)."""
        raise NotImplementedError("Phase 4")

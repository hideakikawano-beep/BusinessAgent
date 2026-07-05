"""Vault writer — single place that renders/writes generated Markdown (Phase 3).

Rules (docs/12):
- write_manual: front-matter Markdown per docs/03 format; upsert manuals table
  (summary kept for the matcher catalog)
- update flow: move current md to .history/<slug>-rev<N>.md BEFORE overwrite,
  bump revision
- copy_asset: shots/ image -> vault/manuals/assets/<slug>/<frame_id>.webp,
  return md-relative path; assets are EXEMPT from purge (purge only touches shots/)
- slug: transliterated task_label, [a-z0-9-], max 60 chars, -2 suffix on clash
- every generated file ends with the 自動生成 footer (docs/03)
"""

from __future__ import annotations

from pathlib import Path


class Vault:
    def __init__(self, cfg, db) -> None:
        raise NotImplementedError("Phase 3")

    def write_manual(self, doc) -> Path:  # doc: manual_builder.ManualDoc
        raise NotImplementedError("Phase 3")

    def copy_asset(self, frame_id: int, slug: str) -> str:
        raise NotImplementedError("Phase 3")

    def append_inbox(self, date_heading: str, facts: list[str]) -> int:
        """Append notable facts to knowledge/inbox.md, skipping lines that
        already exist verbatim (normalized whitespace). Returns #added."""
        raise NotImplementedError("Phase 3")


def make_slug(task_label: str, existing: set[str]) -> str:
    raise NotImplementedError("Phase 3")

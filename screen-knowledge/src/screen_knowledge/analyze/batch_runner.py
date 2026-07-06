"""Nightly Batch API pipeline (Phase 2).

Facts this design relies on (verified 2026-07; docs/11):
- Batch = 50% price; most complete within 1h, max 24h; results kept 29 days
- results are UNORDERED — always join by custom_id (f"session-{id}")
- params use output_config={"format": {"type": "json_schema", "schema": ...}};
  results are validated with SessionAnalysis.model_validate_json
- chunk at 50 sessions/batch, images inline base64 (no Files API)

State machine (docs/03): queued -submit-> submitted -collect ok-> analyzed
/ invalid_request -> failed / other errors & expired -> back to queued.
catch_up() on daemon start: resubmit stale queued, poll submitted, fall back
to the regular API after analysis.batch_fallback_after_h while the PC is on.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CollectReport:
    analyzed: int = 0
    failed: int = 0
    requeued: int = 0
    errors: list[str] = field(default_factory=list)


class BatchRunner:
    def __init__(self, cfg, db, client, analyzer) -> None:
        raise NotImplementedError("Phase 2")

    def submit(self, session_ids: list[int]) -> list[str]:
        """Submit queued sessions in chunks of 50; returns batch_ids."""
        raise NotImplementedError("Phase 2")

    def poll_and_collect(self) -> CollectReport:
        """For each submitted batch: retrieve; if ended, collect results."""
        raise NotImplementedError("Phase 2")

    def collect(self, batch_id: str) -> CollectReport:
        raise NotImplementedError("Phase 2")

    def catch_up(self) -> None:
        raise NotImplementedError("Phase 2")

"""Manual synthesis (Phase 3).

create(): SessionAnalysis(+ steps/image_ref->frame_id mapping) ->
ManualDoc via api.synthesis_model (structured outputs) -> Vault.write_manual
(+ copy_asset per step when with_images).
update(): pass CURRENT manual full text + new analysis -> FULL REWRITE
(never diff-patch; the old revision is preserved in .history/). Keep images
of steps that only exist in the old version.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class ManualStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    frame_id: int | None = Field(
        default=None, description="ステップ画像のframes.id（画像なしはnull）"
    )


class ManualDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    slug: str
    intro: str
    prerequisites: list[str]
    steps: list[ManualStep]
    notes: list[str]
    source_session_ids: list[int]


class ManualBuilder:
    def __init__(self, cfg, db, client, vault, matcher) -> None:
        raise NotImplementedError("Phase 3")

    def create(self, analyses: list, *, with_images: bool) -> Path:
        raise NotImplementedError("Phase 3")

    def update(self, manual_id: int, new_analysis) -> Path:
        raise NotImplementedError("Phase 3")

    def detect_repeats_and_draft(self, lookback_days: int = 14) -> list[Path]:
        """Nightly: group recent worth_documenting sessions (single LLM call);
        draft one manual per group seen >= 2 times and not matching an
        existing manual. Never auto-updates existing manuals (marked flow only).
        """
        raise NotImplementedError("Phase 3")

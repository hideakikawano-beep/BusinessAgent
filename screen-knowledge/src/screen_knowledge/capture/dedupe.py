"""Image-storage decision (pHash dedupe). Pure logic — heavily unit-tested.

Key invariant (docs/00 design decision #1): metadata rows are recorded every
tick regardless; this module only decides whether the IMAGE is stored.
Comparison target is the LAST STORED frame's phash (not the previous tick),
otherwise slow drift never stores.
"""

from __future__ import annotations

import datetime as dt


def compute_phash(image) -> str:
    """64-bit perceptual hash as 16 hex chars (grayscale downscale first)."""
    raise NotImplementedError("Phase 1")


def hamming(phash_a: str, phash_b: str) -> int:
    raise NotImplementedError("Phase 1")


def should_store_image(
    phash: str,
    last_stored_phash: str | None,
    last_stored_at: dt.datetime | None,
    now: dt.datetime,
    window_changed: bool,
    marked: bool,
    cfg,  # config.Config
) -> tuple[bool, str]:
    """Return (store?, stored_reason).

    Store when ANY of (docs/02 判定フロー):
      - no previous stored frame
      - window_changed (after debounce, handled by caller)  -> "window_change"
      - hamming > threshold (marked_phash_threshold if marked) -> "threshold" / "marked"
      - now - last_stored_at >= force_keyframe_s             -> "keyframe"
    Caller applies meeting low-rate and daily cap BEFORE calling this.
    """
    raise NotImplementedError("Phase 1")

"""Image-storage decision (pHash dedupe). Pure logic — heavily unit-tested.

Key invariant (docs/00 design decision #1): metadata rows are recorded every
tick regardless; this module only decides whether the IMAGE is stored.
Comparison target is the LAST STORED frame's phash (not the previous tick),
otherwise slow drift never stores.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import PIL.Image

    from ..config import Config


def compute_phash(image: PIL.Image.Image) -> str:
    """64-bit perceptual hash as 16 hex chars (imagehash converts to grayscale)."""
    import imagehash

    return str(imagehash.phash(image))


def hamming(phash_a: str, phash_b: str) -> int:
    """Hamming distance between two 16-hex-char perceptual hashes."""
    return bin(int(phash_a, 16) ^ int(phash_b, 16)).count("1")


def should_store_image(
    phash: str,
    last_stored_phash: str | None,
    last_stored_at: dt.datetime | None,
    now: dt.datetime,
    window_changed: bool,
    marked: bool,
    cfg: Config,
) -> tuple[bool, str]:
    """Return (store?, stored_reason).

    Store when ANY of (docs/02 判定フロー):
      - no previous stored frame                              -> "keyframe"
      - window_changed (after debounce, handled by caller)    -> "window_change"
      - hamming > threshold (marked_phash_threshold if marked)-> "marked"/"threshold"
      - now - last_stored_at >= force_keyframe_s              -> "keyframe"
    Caller applies meeting low-rate and daily cap BEFORE calling this.
    """
    if last_stored_phash is None or last_stored_at is None:
        return True, "keyframe"

    if window_changed:
        return True, "window_change"

    threshold = cfg.dedupe.marked_phash_threshold if marked else cfg.dedupe.phash_threshold
    if hamming(phash, last_stored_phash) > threshold:
        return True, ("marked" if marked else "threshold")

    if (now - last_stored_at).total_seconds() >= cfg.dedupe.force_keyframe_s:
        return True, "keyframe"

    return False, ""

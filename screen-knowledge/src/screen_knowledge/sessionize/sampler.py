"""Keyframe selection for API analysis (Phase 2).

Rules (docs/11):
- only frames with a stored image (image_path not NULL)
- always include first and last; fill remainder by pHash diversity
  (greedy max-min-distance)
- cap: api.max_images_per_session (12); meeting-dominated sessions cap at 4
- RE-CHECK the exclusion list with the CURRENT config and drop matches
  (docs/04 defense-in-depth — settings may have changed since capture)
"""

from __future__ import annotations

from .sessionizer import FrameRow


def select_keyframes(frames: list[FrameRow], max_images: int = 12, *, cfg=None) -> list[FrameRow]:
    raise NotImplementedError("Phase 2")

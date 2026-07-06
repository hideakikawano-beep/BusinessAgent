from __future__ import annotations

import datetime as dt

from screen_knowledge.capture.dedupe import hamming, should_store_image
from screen_knowledge.config import Config

NOW = dt.datetime(2026, 7, 5, 10, 0, 0, tzinfo=dt.UTC)
FAR = "0000000000000000"
NEAR = "0000000000000001"  # distance 1 from FAR
WIDE = "ffffffffffffffff"  # distance 64 from FAR


def test_hamming():
    assert hamming(FAR, FAR) == 0
    assert hamming(FAR, NEAR) == 1
    assert hamming(FAR, WIDE) == 64


def test_first_frame_always_stored():
    store, reason = should_store_image(FAR, None, None, NOW, False, False, Config())
    assert store and reason == "keyframe"


def test_window_change_forces_store():
    store, reason = should_store_image(
        NEAR, FAR, NOW, NOW, True, False, Config()
    )
    assert store and reason == "window_change"


def test_distance_over_threshold_stores():
    store, reason = should_store_image(WIDE, FAR, NOW, NOW, False, False, Config())
    assert store and reason == "threshold"


def test_marked_uses_marked_threshold_and_reason():
    cfg = Config(dedupe={"phash_threshold": 8, "marked_phash_threshold": 0})
    # distance 1 exceeds marked threshold 0 but not normal threshold 8
    store_marked, reason = should_store_image(NEAR, FAR, NOW, NOW, False, True, cfg)
    assert store_marked and reason == "marked"
    store_normal, _ = should_store_image(NEAR, FAR, NOW, NOW, False, False, cfg)
    assert not store_normal


def test_below_threshold_within_keyframe_skips():
    store, _ = should_store_image(NEAR, FAR, NOW, NOW, False, False, Config())
    assert not store


def test_force_keyframe_after_interval():
    cfg = Config(dedupe={"force_keyframe_s": 300})
    later = NOW + dt.timedelta(seconds=301)
    store, reason = should_store_image(NEAR, FAR, NOW, later, False, False, cfg)
    assert store and reason == "keyframe"

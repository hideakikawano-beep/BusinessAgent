from __future__ import annotations

import datetime as dt

from fakes import FakeClock, make_fake_adapters, make_image

from screen_knowledge.capture.adapters.base import WindowInfo
from screen_knowledge.capture.daemon import CaptureDaemon
from screen_knowledge.config import Config

NOW = dt.datetime(2026, 7, 5, 10, 0, 0, tzinfo=dt.UTC)


def build(db, cfg=None):
    cfg = cfg or Config()
    adapters = make_fake_adapters()
    daemon = CaptureDaemon(cfg, db, adapters, FakeClock(NOW))
    return daemon, adapters


def _count(db, where=""):
    return db.scalar(f"SELECT COUNT(*) FROM frames {where}")


def test_excluded_records_metadata_without_image(db):
    daemon, adapters = build(db)
    adapters.active_window.window = WindowInfo("1Password", "vault", pid=1)
    r = daemon.tick(NOW)
    assert r.recorded and not r.stored_image and r.skipped_reason == "excluded"
    row = db.query_one("SELECT * FROM frames ORDER BY id DESC LIMIT 1")
    assert row["skipped_reason"] == "excluded"
    assert row["image_path"] is None


def test_idle_non_meeting_records_nothing(db):
    daemon, adapters = build(db)
    adapters.idle.seconds = 400  # > idle_pause_after_s (300)
    r = daemon.tick(NOW)
    assert not r.recorded
    assert _count(db) == 0


def test_meeting_app_captures_while_idle(db):
    daemon, adapters = build(db)
    adapters.active_window.window = WindowInfo("zoom.us", "会議", pid=1)
    adapters.idle.seconds = 400
    r = daemon.tick(NOW)
    assert r.recorded and r.stored_image


def test_identical_image_deduped_but_metadata_kept(db):
    daemon, adapters = build(db)
    adapters.screenshot.image = make_image(7)
    now = NOW
    for _ in range(5):
        daemon.tick(now)
        now += dt.timedelta(seconds=30)
    assert _count(db) == 5  # metadata every tick
    assert _count(db, "WHERE image_path IS NOT NULL") == 1  # only first stored (<= 3)


def test_window_change_forces_store(db):
    daemon, adapters = build(db)
    adapters.screenshot.image = make_image(7)  # same image throughout
    adapters.active_window.window = WindowInfo("chrome.exe", "A", pid=1)
    daemon.tick(NOW)  # first -> stored
    daemon.tick(NOW + dt.timedelta(seconds=30))  # same window+image -> skipped
    adapters.active_window.window = WindowInfo("chrome.exe", "B", pid=1)
    daemon.tick(NOW + dt.timedelta(seconds=60))  # window changed -> stored
    assert _count(db, "WHERE image_path IS NOT NULL") == 2
    last = db.query_one(
        "SELECT * FROM frames WHERE image_path IS NOT NULL ORDER BY id DESC LIMIT 1"
    )
    assert last["stored_reason"] == "window_change"


def test_different_image_stores(db):
    daemon, adapters = build(db)
    adapters.screenshot.image = make_image(1)
    daemon.tick(NOW)
    adapters.screenshot.image = make_image(999)
    daemon.tick(NOW + dt.timedelta(seconds=30))
    assert _count(db, "WHERE image_path IS NOT NULL") == 2


def test_pause_records_nothing(db):
    daemon, adapters = build(db)
    daemon.pause(NOW + dt.timedelta(hours=1))
    r = daemon.tick(NOW)
    assert not r.recorded
    assert _count(db) == 0


def test_daily_cap_stops_storing_images(db):
    daemon, adapters = build(db, Config(budget={"daily_stored_frames_cap": 1}))
    adapters.screenshot.image = make_image(1)
    daemon.tick(NOW)  # stored (count now 1)
    adapters.screenshot.image = make_image(2)
    daemon.tick(NOW + dt.timedelta(seconds=30))  # different but cap reached
    assert _count(db) == 2
    assert _count(db, "WHERE image_path IS NOT NULL") == 1


def test_capture_error_recorded_and_loop_survives(db):
    daemon, adapters = build(db)
    adapters.screenshot.raise_next = True
    r = daemon.tick(NOW)
    assert r.recorded and not r.stored_image
    assert r.skipped_reason.startswith("error:")


def test_current_interval_variants(db):
    daemon, adapters = build(db)
    normal = WindowInfo("chrome.exe", "x", pid=1)
    meeting = WindowInfo("zoom.us", "会議", pid=1)
    assert daemon.current_interval(normal) == 30
    assert daemon.current_interval(meeting) == 300
    daemon.toggle_mark(NOW)
    assert daemon.current_interval(normal) == 5  # marked overrides


def test_interval_zero_disables_time_capture(db):
    daemon, _ = build(db, Config(capture={"interval_seconds": 0}))
    win = WindowInfo("chrome.exe", "x", pid=1)
    assert daemon.current_interval(win) is None
    daemon.toggle_mark(NOW)
    assert daemon.current_interval(win) == 5  # marks still capture


def test_toggle_mark_writes_marks_row(db):
    daemon, _ = build(db)
    assert daemon.toggle_mark(NOW) is True
    assert daemon.is_marked()
    assert db.scalar("SELECT COUNT(*) FROM marks WHERE ended_at IS NULL") == 1
    assert daemon.toggle_mark(NOW + dt.timedelta(minutes=5)) is False
    assert db.scalar("SELECT COUNT(*) FROM marks WHERE ended_at IS NULL") == 0

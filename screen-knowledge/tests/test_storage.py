from __future__ import annotations

import datetime as dt
import os

from fakes import make_image
from PIL import Image

from screen_knowledge import paths
from screen_knowledge.capture.storage import FrameStore
from screen_knowledge.config import Config

NOW = dt.datetime(2026, 7, 5, 10, 0, 0, tzinfo=dt.UTC)


def _store(db):
    return FrameStore(Config(), db)


def test_save_webp_path_and_downscale(db):
    store = _store(db)
    big = make_image(1, size=(3000, 2000))
    out = store.save_webp(big, 42, NOW)
    assert out.exists()
    assert out.name == "42.webp"
    assert "2026" in str(out) and out.parent == paths.shots_dir(NOW.date())
    w, h = Image.open(out).size
    assert max(w, h) <= Config().capture.store_long_edge_px
    assert FrameStore.relpath(out).endswith("42.webp")


def test_purge_deletes_old_keeps_fresh(db):
    store = _store(db)
    old = store.save_webp(make_image(1), 1, NOW)
    fresh = store.save_webp(make_image(2), 2, NOW)
    old_ts = (NOW - dt.timedelta(days=40)).timestamp()
    os.utime(old, (old_ts, old_ts))
    os.utime(fresh, (NOW.timestamp(), NOW.timestamp()))
    report = store.purge(30, 999, metadata_days=180, now=NOW)
    assert not old.exists()
    assert fresh.exists()
    assert report.deleted_files == 1


def test_purge_enforces_max_gb(db):
    store = _store(db)
    p1 = store.save_webp(make_image(1), 1, NOW)
    p2 = store.save_webp(make_image(2), 2, NOW)
    os.utime(p1, (NOW.timestamp(), NOW.timestamp()))
    os.utime(p2, (NOW.timestamp(), NOW.timestamp()))
    report = store.purge(9999, 0, metadata_days=180, now=NOW)  # age won't trigger; size 0 wipes
    assert report.deleted_files == 2
    assert not p1.exists() and not p2.exists()


def test_purge_deletes_old_metadata_rows(db):
    store = _store(db)
    db.insert("frames", {"captured_at": (NOW - dt.timedelta(days=200)).isoformat()})
    db.insert("frames", {"captured_at": NOW.isoformat()})
    report = store.purge(30, 999, metadata_days=180, now=NOW)
    assert report.deleted_meta_rows == 1
    assert db.scalar("SELECT COUNT(*) FROM frames") == 1


def test_purge_dry_run_deletes_nothing(db):
    store = _store(db)
    p = store.save_webp(make_image(1), 1, NOW)
    old_ts = (NOW - dt.timedelta(days=40)).timestamp()
    os.utime(p, (old_ts, old_ts))
    report = store.purge(30, 999, metadata_days=180, dry_run=True, now=NOW)
    assert p.exists()  # nothing removed
    assert report.deleted_files == 1  # but counted


def test_purge_never_touches_vault_assets(db):
    store = _store(db)
    asset_dir = paths.manual_assets_dir("some-manual")
    asset_dir.mkdir(parents=True, exist_ok=True)
    asset = asset_dir / "1.webp"
    asset.write_bytes(b"keepme")
    store.save_webp(make_image(1), 1, NOW)
    store.purge(9999, 0, metadata_days=180, now=NOW)  # wipes shots
    assert asset.exists()

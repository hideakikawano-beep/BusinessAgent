from __future__ import annotations

import threading

from screen_knowledge.db import fts5_trigram_available


def test_migrate_idempotent(db):
    db.migrate()  # second call must not error
    tables = {
        r["name"]
        for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for expected in ("frames", "sessions", "marks", "session_analyses", "manuals",
                     "daily_logs", "api_usage", "settings"):
        assert expected in tables


def test_wal_mode(db):
    mode = db.scalar("PRAGMA journal_mode")
    assert str(mode).lower() == "wal"


def test_settings_roundtrip(db):
    assert db.get_setting("missing") is None
    assert db.get_setting("missing", "dflt") == "dflt"
    db.set_setting("k", "v1")
    assert db.get_setting("k") == "v1"
    db.set_setting("k", "v2")  # upsert
    assert db.get_setting("k") == "v2"


def test_insert_and_query(db):
    fid = db.insert(
        "frames",
        {"captured_at": "2026-07-05T10:00:00+00:00", "app_name": "x", "window_title": "t"},
    )
    assert isinstance(fid, int)
    row = db.query_one("SELECT * FROM frames WHERE id=?", (fid,))
    assert row["app_name"] == "x"


def test_writer_lock_concurrent(db):
    def worker():
        for _ in range(20):
            db.insert("frames", {"captured_at": "2026-07-05T10:00:00+00:00"})

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    count = db.scalar("SELECT COUNT(*) FROM frames")
    assert count == 100


def test_fts5_probe_runs(db):
    # Either True or False, but must not raise.
    result = db.read(fts5_trigram_available)
    assert isinstance(result, bool)

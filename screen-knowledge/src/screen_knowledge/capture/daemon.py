"""Capture daemon: the tick loop and worker-thread wiring (Phase 1).

Threading model (docs/02): the main thread runs TrayAdapter.run(); this daemon
runs in a worker thread. All DB writes go through db.Database.write(). An
exception inside a tick is logged + recorded as skipped_reason='error:...' —
the loop never dies.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from ..logsetup import get_logger
from . import dedupe
from .storage import FrameStore

if TYPE_CHECKING:  # pragma: no cover
    import threading

    from ..config import Config
    from ..db import Database
    from .adapters.base import Adapters, WindowInfo


class Clock(Protocol):
    def now(self) -> dt.datetime: ...
    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def now(self) -> dt.datetime:
        return dt.datetime.now().astimezone()

    def sleep(self, seconds: float) -> None:
        import time

        time.sleep(seconds)


@dataclass
class TickResult:
    recorded: bool
    stored_image: bool
    skipped_reason: str | None = None
    frame_id: int | None = None


def _matches(text: str, needles: list[str]) -> bool:
    low = text.lower()
    return any(n and n.lower() in low for n in needles)


class CaptureDaemon:
    """Owns pause state, mark state (marks table), and the tick cadence.

    Cadence: capture.interval_seconds (marked_interval_seconds while a mark is
    active; meeting.capture_interval_s while a meeting app is frontmost;
    interval_seconds == 0 => tick only while marked). Window-change events
    trigger an immediate tick (debounced window_change_debounce_s).
    """

    def __init__(
        self,
        cfg: Config,
        db: Database,
        adapters: Adapters,
        clock: Clock | None = None,
    ) -> None:
        self.cfg = cfg
        self.db = db
        self.adapters = adapters
        self.clock: Clock = clock or SystemClock()
        self.store = FrameStore(cfg, db)
        self.log = get_logger()

        self._last_active_key: tuple[str | None, str | None] | None = None
        self._last_stored_phash: str | None = None
        self._last_stored_at: dt.datetime | None = None
        # run_forever cadence state
        self._last_tick_at: dt.datetime | None = None
        self._last_seen_key: tuple[str | None, str | None] | None = None
        self._last_window_trigger_at: dt.datetime | None = None
        self._poll_seconds = 1.0

    # ------------------------------------------------------------------ state
    def is_paused(self, now: dt.datetime) -> bool:
        val = self.db.get_setting("paused_until")
        if not val:
            return False
        if val == "inf":
            return True
        try:
            until = dt.datetime.fromisoformat(val)
        except ValueError:
            return False
        if now >= until:
            self.db.execute("DELETE FROM settings WHERE key='paused_until'")
            return False
        return True

    def pause(self, until: dt.datetime | None) -> None:
        self.db.set_setting("paused_until", until.isoformat() if until else "inf")

    def resume(self) -> None:
        self.db.execute("DELETE FROM settings WHERE key='paused_until'")

    def is_marked(self) -> bool:
        return self.db.get_setting("mark_active") == "1"

    def toggle_mark(self, now: dt.datetime | None = None) -> bool:
        """Start/stop a mark (marks table). Returns new state (True=marking)."""
        now = now or self.clock.now()
        if self.is_marked():
            self.db.execute(
                "UPDATE marks SET ended_at=? WHERE ended_at IS NULL", (now.isoformat(),)
            )
            self.db.set_setting("mark_active", "0")
            return False
        self.db.insert("marks", {"started_at": now.isoformat()})
        self.db.set_setting("mark_active", "1")
        return True

    # ------------------------------------------------------------- classify
    def is_excluded(self, win: WindowInfo | None) -> bool:
        if win is None:
            return False
        if _matches(win.app_name, self.cfg.exclude.apps):
            return True
        return _matches(win.window_title, self.cfg.exclude.title_keywords)

    def is_meeting(self, win: WindowInfo | None) -> bool:
        if win is None:
            return False
        if _matches(win.app_name, self.cfg.meeting.apps):
            return True
        return _matches(win.window_title, self.cfg.meeting.title_keywords)

    def current_interval(self, win: WindowInfo | None) -> float | None:
        """Seconds between time-based captures, or None when capture is off."""
        marked = self.is_marked()
        continuous = self.cfg.capture.interval_seconds > 0
        if marked:
            return float(self.cfg.capture.marked_interval_seconds)
        if not continuous:
            return None  # continuous disabled; only marks capture
        if self.is_meeting(win):
            return float(self.cfg.meeting.capture_interval_s)
        return float(self.cfg.capture.interval_seconds)

    def _stored_today(self, now: dt.datetime) -> int:
        n = self.db.scalar(
            "SELECT COUNT(*) FROM frames "
            "WHERE image_path IS NOT NULL AND date(captured_at)=date(?)",
            (now.isoformat(),),
        )
        return int(n or 0)

    # ------------------------------------------------------------------ tick
    def tick(self, now: dt.datetime) -> TickResult:
        """One capture attempt (docs/02 キャプチャの判定フロー)."""
        if self.is_paused(now):
            return TickResult(recorded=False, stored_image=False)

        win = self._safe_active_window()
        key = (win.app_name, win.window_title) if win else (None, None)
        window_changed = self._last_active_key is not None and key != self._last_active_key
        self._last_active_key = key
        marked = self.is_marked()

        app_name = win.app_name if win else ""
        window_title = win.window_title if win else ""

        # exclusion -> metadata row only, no image
        if self.is_excluded(win):
            fid = self._insert_frame(
                now, app_name, window_title, None, None, None, None, "excluded", marked
            )
            self._heartbeat(now)
            return TickResult(True, False, "excluded", fid)

        # idle -> record nothing (meeting apps are exempt: no keyboard while talking)
        idle_for = self._safe_idle()
        if idle_for > self.cfg.capture.idle_pause_after_s and not self.is_meeting(win):
            self._heartbeat(now)
            return TickResult(False, False, "idle")

        # capture
        try:
            cap = self.adapters.screenshot.capture_monitor_of(win)
            phash = dedupe.compute_phash(cap.image)
        except Exception as exc:  # never kill the loop
            self.log.exception("capture failed")
            reason = f"error:{exc}"[:200]
            fid = self._insert_frame(
                now, app_name, window_title, None, None, None, None, reason, marked
            )
            self._heartbeat(now)
            return TickResult(True, False, reason, fid)

        store, reason = dedupe.should_store_image(
            phash,
            self._last_stored_phash,
            self._last_stored_at,
            now,
            window_changed,
            marked,
            self.cfg,
        )
        # daily cap: keep recording metadata, stop storing images
        if store and self._stored_today(now) >= self.cfg.budget.daily_stored_frames_cap:
            store, reason = False, ""

        fid = self._insert_frame(
            now, app_name, window_title, cap.monitor_index, phash, None, None, None, marked
        )
        stored = False
        if store:
            out = self.store.save_webp(cap.image, fid, now)
            rel = FrameStore.relpath(out)
            self.db.execute(
                "UPDATE frames SET image_path=?, stored_reason=? WHERE id=?", (rel, reason, fid)
            )
            self._last_stored_phash = phash
            self._last_stored_at = now
            stored = True

        self._heartbeat(now)
        return TickResult(True, stored, None, fid)

    # ------------------------------------------------------------- run loop
    def run_forever(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                now = self.clock.now()
                self._heartbeat(now)
                win = self._safe_active_window()
                if self._due(now, win):
                    self.tick(now)
                    self._last_tick_at = now
            except Exception:
                self.log.exception("tick loop error")
            stop_event.wait(self._poll_seconds)

    def _due(self, now: dt.datetime, win: WindowInfo | None) -> bool:
        if self.is_paused(now):
            return False
        interval = self.current_interval(win)
        marked = self.is_marked()
        active = marked or self.cfg.capture.interval_seconds > 0
        if not active:
            return False

        key = (win.app_name, win.window_title) if win else (None, None)
        window_changed = self._last_seen_key is not None and key != self._last_seen_key
        self._last_seen_key = key

        due_by_time = interval is not None and (
            self._last_tick_at is None
            or (now - self._last_tick_at).total_seconds() >= interval
        )
        due_by_window = False
        if window_changed and self.cfg.capture.on_window_change and self._debounce_ok(now):
            due_by_window = True
            self._last_window_trigger_at = now
        return bool(due_by_time or due_by_window)

    def _debounce_ok(self, now: dt.datetime) -> bool:
        if self._last_window_trigger_at is None:
            return True
        return (
            now - self._last_window_trigger_at
        ).total_seconds() >= self.cfg.capture.window_change_debounce_s

    # ------------------------------------------------------------- helpers
    def _safe_active_window(self) -> WindowInfo | None:
        try:
            return self.adapters.active_window.get_active_window()
        except Exception:
            self.log.exception("active window lookup failed")
            return None

    def _safe_idle(self) -> float:
        try:
            return self.adapters.idle.seconds_since_input()
        except Exception:
            return 0.0

    def _heartbeat(self, now: dt.datetime) -> None:
        self.db.set_setting("daemon_heartbeat", now.isoformat())

    def _insert_frame(
        self,
        now: dt.datetime,
        app_name: str,
        window_title: str,
        monitor_index: int | None,
        phash: str | None,
        image_path: str | None,
        stored_reason: str | None,
        skipped_reason: str | None,
        marked: bool,
    ) -> int:
        return self.db.insert(
            "frames",
            {
                "captured_at": now.isoformat(),
                "app_name": app_name,
                "window_title": window_title,
                "monitor_index": monitor_index,
                "phash": phash,
                "image_path": image_path,
                "stored_reason": stored_reason,
                "skipped_reason": skipped_reason,
                "is_marked": 1 if marked else 0,
            },
        )

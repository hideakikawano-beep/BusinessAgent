"""Capture daemon: the tick loop and worker-thread wiring (Phase 1).

Threading model (docs/02): main thread runs TrayAdapter.run(); this daemon
runs in a worker thread. All DB writes go through db.Database.write().
Exceptions inside a tick are logged + recorded as skipped_reason='error:...'
— the loop never dies.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol


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


class CaptureDaemon:
    """Owns pause state, mark state (marks table), and the tick cadence.

    Cadence: capture.interval_seconds (marked_interval_seconds while a mark is
    active; meeting.capture_interval_s image rate while a meeting app is
    frontmost; interval_seconds==0 => tick only while marked).
    Window-change events trigger an immediate tick (debounced
    window_change_debounce_s).
    """

    def __init__(self, cfg, db, adapters, clock: Clock | None = None) -> None:
        raise NotImplementedError("Phase 1")

    # -- controls (called from tray menu / hotkey) --
    def pause(self, until: dt.datetime | None) -> None:
        raise NotImplementedError("Phase 1")

    def resume(self) -> None:
        raise NotImplementedError("Phase 1")

    def toggle_mark(self) -> bool:
        """Start/stop a mark (marks table). Returns new state (True=marking)."""
        raise NotImplementedError("Phase 1")

    # -- loop --
    def tick(self, now: dt.datetime) -> TickResult:
        """One capture attempt. Pure-ish; the unit-test surface.

        Flow (docs/02 キャプチャの判定フロー): paused? -> active window ->
        exclusion -> idle (meeting exception) -> capture -> dedupe ->
        frames row (+ image) -> heartbeat.
        """
        raise NotImplementedError("Phase 1")

    def run_forever(self, stop_event) -> None:  # threading.Event
        raise NotImplementedError("Phase 1")

"""Frozen OS-adapter contracts (docs/02-architecture.md).

Do NOT change these signatures without updating docs/02 and the fakes in
tests/fakes.py. Non-adapter modules must depend only on these Protocols.
"""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    import PIL.Image


@dataclass
class WindowInfo:
    app_name: str          # e.g. "chrome.exe" / "Google Chrome"
    window_title: str      # includes browser tab title; "" when unavailable
    pid: int
    bounds: tuple[int, int, int, int] | None = None  # (left, top, w, h) physical px


@dataclass
class Capture:
    image: "PIL.Image.Image"
    monitor_index: int
    physical_scale: float  # logical->physical px ratio (Retina etc.)


class PermissionStatus(enum.Enum):
    OK = "ok"
    MISSING_SCREEN_RECORDING = "missing_screen_recording"  # macOS only
    UNKNOWN = "unknown"


class ScreenshotAdapter(Protocol):
    def capture_monitor_of(self, win: WindowInfo | None) -> Capture:
        """Capture ONLY the monitor containing `win` (primary if unknown).

        Never use the all-monitors union (mss.monitors[0]).
        """
        ...

    def preflight(self) -> PermissionStatus:
        """Cheap permission check; on macOS must detect missing 画面収録."""
        ...


class ActiveWindowAdapter(Protocol):
    def get_active_window(self) -> WindowInfo | None: ...


class IdleAdapter(Protocol):
    def seconds_since_input(self) -> float: ...


@dataclass
class TrayMenuItem:
    label: str
    action: Callable[[], None] | None = None   # None => disabled entry
    checked: bool = False


@dataclass
class TrayMenuSpec:
    status_line: str
    items: list[TrayMenuItem] = field(default_factory=list)


class TrayAdapter(Protocol):
    def run(self, menu: TrayMenuSpec) -> None:
        """Blocks the MAIN thread with the tray event loop (rumps requires it)."""
        ...

    def update_status(self, text: str) -> None:
        """Update the status line (state / today's count / monthly cost)."""
        ...


class HotkeyAdapter(Protocol):
    def register(self, combo: str, on_press: Callable[[], None]) -> bool:
        """Register a global hotkey. False (with a log) on failure — never raise
        in a way that kills the daemon."""
        ...


@dataclass
class Adapters:
    screenshot: ScreenshotAdapter
    active_window: ActiveWindowAdapter
    idle: IdleAdapter
    tray: TrayAdapter
    hotkey: HotkeyAdapter | None = None  # None where unsupported/disabled

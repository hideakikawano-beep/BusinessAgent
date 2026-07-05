"""macOS adapters (Phase 1).

Implementation notes (docs/10-phase1-capture.md):
- Screen recording permission is the ONLY mandatory permission. Without it,
  captures silently contain wallpaper only and window titles come back empty —
  preflight via CGPreflightScreenCaptureAccess / CGRequestScreenCaptureAccess
  (pyobjc symbol names 要確認) PLUS the heuristic self-test in `sk doctor`.
- App name: NSWorkspace.sharedWorkspace().frontmostApplication() (no permission).
- Window title/bounds: CGWindowListCopyWindowInfo (kCGWindowName requires the
  screen-recording permission; degrade to app-name-only with title="").
- Idle: CGEventSourceSecondsSinceLastEventType.
- Tray: rumps (NOT pystray — main-thread and menu-update limitations).
  rumps.App.run() must own the main thread.
- Screenshot: mss returns physical (Retina) pixels; downscale happens in storage.
- Hotkey: NOT implemented in Phase 1 (Accessibility friction; Phase 3 optional).
"""

from __future__ import annotations

from .base import (
    Capture,
    PermissionStatus,
    TrayMenuSpec,
    WindowInfo,
)


class MacScreenshotAdapter:
    def capture_monitor_of(self, win: WindowInfo | None) -> Capture:
        raise NotImplementedError("Phase 1")

    def preflight(self) -> PermissionStatus:
        raise NotImplementedError("Phase 1")


class MacActiveWindowAdapter:
    def get_active_window(self) -> WindowInfo | None:
        raise NotImplementedError("Phase 1")


class MacIdleAdapter:
    def seconds_since_input(self) -> float:
        raise NotImplementedError("Phase 1")


class MacTrayAdapter:
    def run(self, menu: TrayMenuSpec) -> None:
        raise NotImplementedError("Phase 1")

    def update_status(self, text: str) -> None:
        raise NotImplementedError("Phase 1")

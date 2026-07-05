"""Windows adapters (Phase 1).

Implementation notes (docs/10-phase1-capture.md):
- At import/startup call SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)
  via ctypes; fall back to shcore.SetProcessDpiAwareness(2). 要確認: build
  availability — record the result in docs/00.
- Active window: GetForegroundWindow + GetWindowText + GetWindowThreadProcessId,
  exe name via psutil.
- Idle: GetLastInputInfo.
- Screenshot: mss (instance owned by the capture thread; not shared).
- Tray: pystray. Hotkey: pynput (no elevation needed).
"""

from __future__ import annotations

from .base import (
    Capture,
    PermissionStatus,
    TrayMenuSpec,
    WindowInfo,
)


def set_dpi_awareness() -> None:
    """Per-Monitor-V2 DPI awareness; must run before any capture."""
    raise NotImplementedError("Phase 1")


class WindowsScreenshotAdapter:
    def capture_monitor_of(self, win: WindowInfo | None) -> Capture:
        raise NotImplementedError("Phase 1")

    def preflight(self) -> PermissionStatus:
        return PermissionStatus.OK  # no special permission on Windows


class WindowsActiveWindowAdapter:
    def get_active_window(self) -> WindowInfo | None:
        raise NotImplementedError("Phase 1")


class WindowsIdleAdapter:
    def seconds_since_input(self) -> float:
        raise NotImplementedError("Phase 1")


class WindowsTrayAdapter:
    def run(self, menu: TrayMenuSpec) -> None:
        raise NotImplementedError("Phase 1")

    def update_status(self, text: str) -> None:
        raise NotImplementedError("Phase 1")


class WindowsHotkeyAdapter:
    def register(self, combo: str, on_press) -> bool:
        raise NotImplementedError("Phase 1")

"""Windows adapters (Phase 1). All Win32/GUI imports are lazy.

Implementation notes (docs/10-phase1-capture.md):
- Startup DPI awareness: SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)
  via ctypes; fall back to shcore.SetProcessDpiAwareness(2). 要確認 build support.
- Active window: GetForegroundWindow + GetWindowText + GetWindowThreadProcessId,
  exe name via psutil.
- Idle: GetLastInputInfo.
- Screenshot: mss (instance owned by the capture thread; not shared).
- Tray: pystray. Hotkey: pynput (no elevation needed).
"""

from __future__ import annotations

from collections.abc import Callable

from .base import Capture, PermissionStatus, TrayMenuSpec, WindowInfo


def set_dpi_awareness() -> None:
    """Per-Monitor-V2 DPI awareness; must run before any capture."""
    import ctypes

    try:
        # PER_MONITOR_AWARE_V2 = -4
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        except Exception:
            pass


def _monitor_for(sct, win: WindowInfo | None):
    monitors = sct.monitors  # [0]=virtual union, [1..]=physical
    if win is None or win.bounds is None or len(monitors) < 2:
        return monitors[1] if len(monitors) >= 2 else monitors[0]
    left, top, w, h = win.bounds
    cx, cy = left + w // 2, top + h // 2
    for mon in monitors[1:]:
        if (
            mon["left"] <= cx < mon["left"] + mon["width"]
            and mon["top"] <= cy < mon["top"] + mon["height"]
        ):
            return mon
    return monitors[1]


class WindowsScreenshotAdapter:
    def __init__(self) -> None:
        self._sct = None

    def _mss(self):
        if self._sct is None:
            import mss

            self._sct = mss.mss()
        return self._sct

    def capture_monitor_of(self, win: WindowInfo | None) -> Capture:
        from PIL import Image

        sct = self._mss()
        mon = _monitor_for(sct, win)
        idx = sct.monitors.index(mon)
        shot = sct.grab(mon)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return Capture(image=img, monitor_index=idx, physical_scale=1.0)

    def preflight(self) -> PermissionStatus:
        return PermissionStatus.OK  # no special permission on Windows


class WindowsActiveWindowAdapter:
    def get_active_window(self) -> WindowInfo | None:
        import psutil
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        title = win32gui.GetWindowText(hwnd) or ""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            pid = 0
        app = ""
        try:
            app = psutil.Process(pid).name()
        except Exception:
            pass
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            bounds = (left, top, right - left, bottom - top)
        except Exception:
            bounds = None
        return WindowInfo(app_name=app, window_title=title, pid=pid, bounds=bounds)


class WindowsIdleAdapter:
    def seconds_since_input(self) -> float:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        millis = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return max(0.0, millis / 1000.0)


class WindowsTrayAdapter:
    def __init__(self) -> None:
        self._icon = None

    def run(self, menu: TrayMenuSpec) -> None:
        import pystray
        from PIL import Image

        def build_menu():
            import pystray as ps

            return ps.Menu(
                *[
                    ps.MenuItem(
                        item.label,
                        (lambda a: (lambda icon, _i: a()))(item.action)
                        if item.action
                        else None,
                        checked=(lambda it: (lambda _i: it.checked))(item),
                        enabled=item.action is not None,
                    )
                    for item in menu.items
                ]
            )

        image = Image.new("RGB", (64, 64), (30, 90, 160))
        self._icon = pystray.Icon("screen_knowledge", image, menu.status_line, build_menu())
        self._icon.run()

    def update_status(self, text: str) -> None:
        if self._icon is not None:
            self._icon.title = text
            try:
                self._icon.update_menu()
            except Exception:
                pass

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()


class WindowsHotkeyAdapter:
    def register(self, combo: str, on_press: Callable[[], None]) -> bool:
        try:
            from pynput import keyboard

            listener = keyboard.GlobalHotKeys({combo: on_press})
            listener.start()
            return True
        except Exception:
            return False

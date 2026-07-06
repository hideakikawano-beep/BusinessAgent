"""macOS adapters (Phase 1). All Quartz/AppKit/GUI imports are lazy.

Implementation notes (docs/10-phase1-capture.md):
- Screen recording permission is the ONLY mandatory permission. Without it,
  captures silently contain wallpaper only and window titles come back empty —
  preflight via CGPreflightScreenCaptureAccess (pyobjc symbol 要確認) PLUS the
  heuristic self-test in `sk doctor`.
- App name: NSWorkspace.frontmostApplication() (no permission).
- Window title/bounds: CGWindowListCopyWindowInfo (kCGWindowName needs the
  screen-recording permission; degrade to app-name-only with title="").
- Idle: CGEventSourceSecondsSinceLastEventType.
- Tray: rumps (NOT pystray — main-thread/menu-update limits). rumps owns the
  main thread.
- Hotkey: NOT implemented in Phase 1 (Accessibility friction; Phase 3 optional).
"""

from __future__ import annotations

from .base import Capture, PermissionStatus, TrayMenuSpec, WindowInfo


def _monitor_for(sct, win: WindowInfo | None):
    monitors = sct.monitors
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


class MacScreenshotAdapter:
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
        # Retina: mss returns physical pixels; downscale happens in storage.
        scale = getattr(shot, "width", img.width) / max(1, mon["width"])
        return Capture(image=img, monitor_index=idx, physical_scale=float(scale) or 1.0)

    def preflight(self) -> PermissionStatus:
        try:
            import Quartz

            fn = getattr(Quartz, "CGPreflightScreenCaptureAccess", None)
            if fn is None:
                return PermissionStatus.UNKNOWN
            return PermissionStatus.OK if fn() else PermissionStatus.MISSING_SCREEN_RECORDING
        except Exception:
            return PermissionStatus.UNKNOWN


class MacActiveWindowAdapter:
    def get_active_window(self) -> WindowInfo | None:
        try:
            from AppKit import NSWorkspace

            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            app_name = app.localizedName() if app else ""
            pid = int(app.processIdentifier()) if app else 0
        except Exception:
            app_name, pid = "", 0

        title, bounds = "", None
        try:
            import Quartz

            opts = (
                Quartz.kCGWindowListOptionOnScreenOnly
                | Quartz.kCGWindowListExcludeDesktopElements
            )
            for w in Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID) or []:
                owner = int(w.get("kCGWindowOwnerPID", -1))
                if owner == pid and w.get("kCGWindowLayer", 1) == 0:
                    title = w.get("kCGWindowName", "") or ""
                    b = w.get("kCGWindowBounds")
                    if b:
                        bounds = (int(b["X"]), int(b["Y"]), int(b["Width"]), int(b["Height"]))
                    break
        except Exception:
            pass
        return WindowInfo(app_name=app_name, window_title=title, pid=pid, bounds=bounds)


class MacIdleAdapter:
    def seconds_since_input(self) -> float:
        try:
            import Quartz

            # kCGAnyInputEventType = 0xFFFFFFFF ; kCGEventSourceStateHIDSystemState = 1
            return float(
                Quartz.CGEventSourceSecondsSinceLastEventType(1, 0xFFFFFFFF)
            )
        except Exception:
            return 0.0


class MacTrayAdapter:
    def __init__(self) -> None:
        self._app = None

    def run(self, menu: TrayMenuSpec) -> None:
        import rumps

        app = rumps.App(menu.status_line, quit_button=None)
        for item in menu.items:
            if item.action is None:
                app.menu.add(rumps.MenuItem(item.label))
            else:
                cb = (lambda a: (lambda _s: a()))(item.action)
                app.menu.add(rumps.MenuItem(item.label, callback=cb))
        self._app = app
        app.run()

    def update_status(self, text: str) -> None:
        if self._app is not None:
            self._app.title = text

    def stop(self) -> None:
        try:
            import rumps

            rumps.quit_application()
        except Exception:
            pass

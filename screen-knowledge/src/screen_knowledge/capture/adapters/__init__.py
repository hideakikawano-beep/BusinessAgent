"""OS adapters. All OS-specific code lives here; everything else is portable.

base.py    — frozen Protocols (docs/02-architecture.md)
windows.py — Win32 implementations (mss, GetForegroundWindow, GetLastInputInfo,
             pystray tray, per-monitor-v2 DPI awareness at startup)
macos.py   — Quartz implementations (mss, NSWorkspace, CGWindowListCopyWindowInfo,
             CGEventSource idle, screen-recording preflight, rumps tray)
factory.py — sys.platform switch returning the Adapters bundle
"""

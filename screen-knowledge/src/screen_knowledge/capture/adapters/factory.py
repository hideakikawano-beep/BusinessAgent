"""Adapter factory — the single sys.platform switch (docs/02)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from .base import Adapters

if TYPE_CHECKING:  # pragma: no cover
    from ...config import Config


def make_adapters(cfg: Config) -> Adapters:
    """Return the OS-appropriate Adapters bundle.

    - win32: Windows* adapters + pynput hotkey (if hotkey.enabled_windows)
    - darwin: Mac* adapters, hotkey=None in Phase 1 (Phase 3 optional)
    - anything else: raise a clear Japanese error (unsupported OS)
    """
    if sys.platform == "win32":
        from .windows import (
            WindowsActiveWindowAdapter,
            WindowsHotkeyAdapter,
            WindowsIdleAdapter,
            WindowsScreenshotAdapter,
            WindowsTrayAdapter,
            set_dpi_awareness,
        )

        set_dpi_awareness()
        hotkey = WindowsHotkeyAdapter() if cfg.hotkey.enabled_windows else None
        return Adapters(
            screenshot=WindowsScreenshotAdapter(),
            active_window=WindowsActiveWindowAdapter(),
            idle=WindowsIdleAdapter(),
            tray=WindowsTrayAdapter(),
            hotkey=hotkey,
        )

    if sys.platform == "darwin":
        from .macos import (
            MacActiveWindowAdapter,
            MacIdleAdapter,
            MacScreenshotAdapter,
            MacTrayAdapter,
        )

        return Adapters(
            screenshot=MacScreenshotAdapter(),
            active_window=MacActiveWindowAdapter(),
            idle=MacIdleAdapter(),
            tray=MacTrayAdapter(),
            hotkey=None,  # Phase 3 (Accessibility permission)
        )

    raise RuntimeError(
        f"未対応のOSです: {sys.platform}。ScreenKnowledge は Windows / macOS のみ対応しています。"
    )

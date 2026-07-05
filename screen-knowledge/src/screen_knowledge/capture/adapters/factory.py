"""Adapter factory — the single sys.platform switch (docs/02)."""

from __future__ import annotations

from .base import Adapters


def make_adapters(cfg) -> Adapters:  # cfg: config.Config
    """Return the OS-appropriate Adapters bundle.

    - win32: Windows* adapters + pynput hotkey (if hotkey.enabled_windows)
    - darwin: Mac* adapters, hotkey=None in Phase 1 (Phase 3 optional)
    - anything else: raise a clear Japanese error (unsupported OS)
    """
    raise NotImplementedError("Phase 1")
